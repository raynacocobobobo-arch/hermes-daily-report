#!/bin/bash
# Hermes Daily Report — 自动同步脚本 v2.0
# 每天 22:00 由 cron 触发
# 1. 同步研报 JSON → data/
# 2. 同步原始字幕 → subtitles/YYYY-MM-DD/ + index.json
# 3. git push → GitHub 私有仓库

set -euo pipefail

REPO_DIR="/home/ubuntu/projects/hermes-daily-report"
SOURCE_JSON="/home/ubuntu/Desktop/hermes/研报"
SOURCE_SUB="/home/ubuntu/Desktop/hermes/研报/字幕"
SSH_KEY="/home/ubuntu/.ssh/hermes_daily_report_ed25519"
TODAY=$(date +%Y-%m-%d)
LOG_FILE="$REPO_DIR/scripts/sync.log"
MAX_FILE_SIZE=$((10 * 1024 * 1024))  # 10MB

# 限制日志行数
tail -n 500 "$LOG_FILE" 2>/dev/null > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE" || true

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# ── 安全: 拒绝私密文件 ──
reject_sensitive() {
    local f="$1"
    local name=$(basename "$f")
    local patterns=("cookie" "token" "api.key" "password" "secret" "private.key" "id_rsa" "id_ed25519" ".env" "config.yaml" "credentials" "auth.json")
    for p in "${patterns[@]}"; do
        if echo "$name" | grep -qi "$p"; then
            log "⛔ 拒绝私密文件: $name"
            return 1
        fi
    done
    return 0
}

log "========== 同步开始 =========="

# ── 1. git pull ──
cd "$REPO_DIR"
export GIT_SSH_COMMAND="ssh -i $SSH_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes"
git pull origin main 2>&1 | tee -a "$LOG_FILE" || log "⚠ pull失败（可能首次或冲突）"

ANY_CHANGE=false

# ═══════════════════════════════════════
# 阶段A: 研报 JSON
# ═══════════════════════════════════════
log "── 阶段A: 研报JSON ──"
JSON_COUNT=0
for f in "$SOURCE_JSON/$TODAY"*.json; do
    [ -f "$f" ] || continue
    dest="$REPO_DIR/data/$(basename "$f")"
    cp "$f" "$dest"
    log "✅ JSON: $(basename "$f")"
    JSON_COUNT=$((JSON_COUNT + 1))
    ANY_CHANGE=true
done
[ "$JSON_COUNT" -eq 0 ] && log "ℹ 无当日研报JSON"

# ═══════════════════════════════════════
# 阶段B: 原始字幕
# ═══════════════════════════════════════
log "── 阶段B: 原始字幕 ──"
SUB_DIR="$SOURCE_SUB/$TODAY"

if [ ! -d "$SUB_DIR" ]; then
    log "⚠ 字幕目录不存在: $SUB_DIR (跳过)"
else
    DEST_SUB="$REPO_DIR/subtitles/$TODAY"
    mkdir -p "$DEST_SUB"

    SUB_COUNT=0
    SKIP_COUNT=0
    REJECT_COUNT=0
    INDEX_ENTRIES=()

    for f in "$SUB_DIR"/*.txt; do
        [ -f "$f" ] || continue
        fname=$(basename "$f")

        # 安全检查
        if ! reject_sensitive "$f"; then
            REJECT_COUNT=$((REJECT_COUNT + 1))
            continue
        fi

        # 大小检查
        fsize=$(stat -c%s "$f")
        if [ "$fsize" -gt "$MAX_FILE_SIZE" ]; then
            log "⛔ 超过10MB: $fname ($((fsize/1024/1024))MB)"
            REJECT_COUNT=$((REJECT_COUNT + 1))
            continue
        fi

        dest="$DEST_SUB/$fname"

        # 去重: 目标已存在且内容相同则跳过
        if [ -f "$dest" ]; then
            if cmp -s "$f" "$dest"; then
                SKIP_COUNT=$((SKIP_COUNT + 1))
                continue
            fi
        fi

        cp "$f" "$dest"
        sha=$(sha256sum "$f" | awk '{print $1}')

        # 提取UP主名和标题（文件格式: UP主名 日期 第N篇.txt）
        up_name=$(echo "$fname" | sed "s/ $TODAY.*//")
        # 从源文件第2行提取标题
        title=$(head -2 "$f" | tail -1 | sed 's/^标题：//' | sed 's/^[[:space:]]*//')

        INDEX_ENTRIES+=("$(jq -n \
            --arg src "$fname" \
            --arg up "$up_name" \
            --arg title "$title" \
            --arg orig "$f" \
            --arg dest "$dest" \
            --arg sha "$sha" \
            --argjson size "$fsize" \
            '{
                source: $src,
                up_name: $up,
                title: $title,
                original_path: $orig,
                repository_path: $dest,
                format: "txt",
                size_bytes: $size,
                sha256: $sha
            }')")

        SUB_COUNT=$((SUB_COUNT + 1))
        ANY_CHANGE=true
    done

    # 生成 index.json
    INDEX_PATH="$DEST_SUB/index.json"
    GENERATED_AT=$(date -Iseconds)
    jq -n \
        --arg date "$TODAY" \
        --arg generated "$GENERATED_AT" \
        --argjson total "$SUB_COUNT" \
        --argjson skipped "$SKIP_COUNT" \
        --argjson rejected "$REJECT_COUNT" \
        --arg source_dir "$SUB_DIR" \
        --argjson entries "$(printf '%s\n' "${INDEX_ENTRIES[@]}" | jq -s .)" \
        '{
            date: $date,
            generated_at: $generated,
            total: $total,
            skipped: $skipped,
            rejected: $rejected,
            source_directory: $source_dir,
            entries: $entries
        }' > "$INDEX_PATH"

    log "📋 字幕: $SUB_COUNT 新增, $SKIP_COUNT 跳过, $REJECT_COUNT 拒绝"
    log "📋 index.json: $INDEX_PATH"
fi

# ═══════════════════════════════════════
# 阶段C: 提交推送
# ═══════════════════════════════════════
if ! $ANY_CHANGE; then
    log "ℹ 无任何变更，跳过推送"
    exit 0
fi

cd "$REPO_DIR"
git add data/ subtitles/ 2>/dev/null || true

if git diff --cached --quiet; then
    log "ℹ git无变更"
    exit 0
fi

SUMMARY=""
[ "$JSON_COUNT" -gt 0 ] && SUMMARY="${SUMMARY}JSON:${JSON_COUNT} "
[ "${SUB_COUNT:-0}" -gt 0 ] && SUMMARY="${SUMMARY}字幕:${SUB_COUNT}"

git commit -m "同步 $TODAY ($SUMMARY)" 2>&1 | tee -a "$LOG_FILE"

# 推送（最多3次重试）
for i in 1 2 3; do
    if git push origin main 2>&1 | tee -a "$LOG_FILE"; then
        log "🎉 推送成功 ($SUMMARY)"
        exit 0
    fi
    log "⚠ 推送失败，第${i}次重试..."
    sleep 15
done

log "❌ 推送失败（已重试3次）"
exit 1