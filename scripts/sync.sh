#!/usr/bin/env bash
# Hermes Daily Report — server-to-GitHub sync
# Recommended server schedule: 22:15 Asia/Shanghai.

set -euo pipefail

export TZ="${HERMES_TIMEZONE:-Asia/Shanghai}"

HERMES_REPO_DIR="${HERMES_REPO_DIR:-/home/ubuntu/projects/hermes-daily-report}"
HERMES_SOURCE_JSON="${HERMES_SOURCE_JSON:-/home/ubuntu/Desktop/hermes/研报}"
HERMES_SOURCE_SUB="${HERMES_SOURCE_SUB:-/home/ubuntu/Desktop/hermes/研报/字幕}"
HERMES_SSH_KEY="${HERMES_SSH_KEY:-/home/ubuntu/.ssh/hermes_daily_report_ed25519}"
TARGET_DATE="${1:-$(date +%F)}"
LOG_FILE="$HERMES_REPO_DIR/scripts/sync.log"
MAX_FILE_SIZE=$((10 * 1024 * 1024))

if [[ ! "$TARGET_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "Invalid date: $TARGET_DATE (expected YYYY-MM-DD)" >&2
    exit 2
fi

mkdir -p "$HERMES_REPO_DIR/scripts" "$HERMES_REPO_DIR/data" "$HERMES_REPO_DIR/subtitles"

# Keep the local log bounded. The log is not added to git.
tail -n 500 "$LOG_FILE" 2>/dev/null > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE" || true

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] $*" | tee -a "$LOG_FILE"
}

reject_sensitive() {
    local file="$1"
    local name
    local pattern
    name=$(basename "$file")
    local patterns=(
        "cookie" "token" "api.key" "password" "secret" "private.key"
        "id_rsa" "id_ed25519" ".env" "config.yaml" "credentials" "auth.json"
    )
    for pattern in "${patterns[@]}"; do
        if grep -qi -- "$pattern" <<< "$name"; then
            log "⛔ 拒绝私密文件: $name"
            return 1
        fi
    done
    return 0
}

extract_up_name() {
    local file="$1"
    local filename="$2"
    local value
    value=$(sed -n -E 's/^UP主[：:][[:space:]]*//p' "$file" | head -n 1)
    if [[ -n "$value" ]]; then
        printf '%s' "$value"
        return
    fi

    # Example: 财经高一截 8.7 第一篇.txt -> 财经高一截
    value=$(sed -E 's/[[:space:]]+[0-9]{1,2}\.[0-9]{1,2}[[:space:]]+第[^[:space:]]+篇\.txt$//' <<< "$filename")
    printf '%s' "${value%.txt}"
}

extract_title() {
    local file="$1"
    local value
    value=$(sed -n -E 's/^标题[：:][[:space:]]*//p' "$file" | head -n 1)
    if [[ -n "$value" ]]; then
        printf '%s' "$value"
        return
    fi

    # Legacy subtitle files usually put the title on the first non-empty line.
    awk '
        NF {
            line=$0
            sub(/^[[:space:]]+/, "", line)
            sub(/[[:space:]]+$/, "", line)
            if (line !~ /^UP主[：:]/) {
                print line
                exit
            }
        }
    ' "$file"
}

log "========== 同步开始: $TARGET_DATE =========="

cd "$HERMES_REPO_DIR"
export GIT_SSH_COMMAND="ssh -i $HERMES_SSH_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes"

# Never continue on a conflicted or failed pull: a blind push could overwrite newer work.
if ! git pull --ff-only origin main 2>&1 | tee -a "$LOG_FILE"; then
    log "❌ git pull --ff-only 失败，停止同步"
    exit 1
fi

ANY_CHANGE=false
JSON_TOTAL=0
JSON_CHANGED=0
SUB_TOTAL=0
SUB_CHANGED=0
SUB_UNCHANGED=0
SUB_REJECTED=0

log "── 阶段A: 研报 JSON ──"
for file in "$HERMES_SOURCE_JSON/$TARGET_DATE"*.json; do
    [[ -f "$file" ]] || continue
    JSON_TOTAL=$((JSON_TOTAL + 1))

    if ! reject_sensitive "$file"; then
        continue
    fi

    size=$(stat -c%s "$file")
    if (( size > MAX_FILE_SIZE )); then
        log "⛔ JSON 超过10MB: $(basename "$file")"
        continue
    fi

    destination="$HERMES_REPO_DIR/data/$(basename "$file")"
    if [[ -f "$destination" ]] && cmp -s "$file" "$destination"; then
        continue
    fi

    cp "$file" "$destination"
    JSON_CHANGED=$((JSON_CHANGED + 1))
    ANY_CHANGE=true
    log "✅ JSON: $(basename "$file")"
done

if (( JSON_TOTAL == 0 )); then
    log "ℹ 无当日研报 JSON"
else
    log "📋 JSON: $JSON_TOTAL 个，$JSON_CHANGED 个有变化"
fi

log "── 阶段B: 原始字幕 ──"
SOURCE_DAY_DIR="$HERMES_SOURCE_SUB/$TARGET_DATE"

if [[ ! -d "$SOURCE_DAY_DIR" ]]; then
    log "⚠ 字幕目录不存在: $SOURCE_DAY_DIR（跳过）"
else
    DEST_DAY_DIR="$HERMES_REPO_DIR/subtitles/$TARGET_DATE"
    mkdir -p "$DEST_DAY_DIR"
    INDEX_ENTRIES=()

    # Build the index from every accepted source file, including unchanged files.
    # This prevents a partial rerun from shrinking index.json.
    shopt -s nullglob
    for file in "$SOURCE_DAY_DIR"/*.txt; do
        filename=$(basename "$file")

        if ! reject_sensitive "$file"; then
            SUB_REJECTED=$((SUB_REJECTED + 1))
            continue
        fi

        size=$(stat -c%s "$file")
        if (( size > MAX_FILE_SIZE )); then
            log "⛔ 字幕超过10MB: $filename"
            SUB_REJECTED=$((SUB_REJECTED + 1))
            continue
        fi

        destination="$DEST_DAY_DIR/$filename"
        if [[ -f "$destination" ]] && cmp -s "$file" "$destination"; then
            SUB_UNCHANGED=$((SUB_UNCHANGED + 1))
        else
            cp "$file" "$destination"
            SUB_CHANGED=$((SUB_CHANGED + 1))
            ANY_CHANGE=true
            log "✅ 字幕: $filename"
        fi

        sha=$(sha256sum "$destination" | awk '{print $1}')
        up_name=$(extract_up_name "$file" "$filename")
        title=$(extract_title "$file")
        repository_path="subtitles/$TARGET_DATE/$filename"

        INDEX_ENTRIES+=("$(jq -cn \
            --arg source "$filename" \
            --arg up_name "$up_name" \
            --arg title "$title" \
            --arg repository_path "$repository_path" \
            --arg sha256 "$sha" \
            --argjson size_bytes "$size" \
            '{
                source: $source,
                up_name: $up_name,
                title: $title,
                repository_path: $repository_path,
                format: "txt",
                size_bytes: $size_bytes,
                sha256: $sha256
            }')")
    done
    shopt -u nullglob

    SUB_TOTAL=${#INDEX_ENTRIES[@]}
    if (( SUB_TOTAL == 0 )); then
        ENTRIES_JSON='[]'
    else
        ENTRIES_JSON=$(printf '%s\n' "${INDEX_ENTRIES[@]}" | jq -s 'sort_by(.source)')
    fi

    INDEX_PATH="$DEST_DAY_DIR/index.json"
    INDEX_TMP=$(mktemp "$DEST_DAY_DIR/.index.tmp.XXXXXX")
    jq -n \
        --arg schema_version "2.1" \
        --arg date "$TARGET_DATE" \
        --arg generated_at "$(date -Iseconds)" \
        --arg source_directory "subtitles/$TARGET_DATE" \
        --argjson total "$SUB_TOTAL" \
        --argjson rejected "$SUB_REJECTED" \
        --argjson entries "$ENTRIES_JSON" \
        '{
            schema_version: $schema_version,
            date: $date,
            generated_at: $generated_at,
            total: $total,
            rejected: $rejected,
            source_directory: $source_directory,
            entries: $entries
        }' > "$INDEX_TMP"

    INDEX_CHANGED=true
    if [[ -f "$INDEX_PATH" ]] && jq -e . "$INDEX_PATH" >/dev/null 2>&1; then
        EXISTING_SEMANTIC=$(jq -S 'del(.generated_at, .changed, .skipped)' "$INDEX_PATH")
        CANDIDATE_SEMANTIC=$(jq -S 'del(.generated_at, .changed, .skipped)' "$INDEX_TMP")
        if [[ "$EXISTING_SEMANTIC" == "$CANDIDATE_SEMANTIC" ]]; then
            INDEX_CHANGED=false
        fi
    fi

    if $INDEX_CHANGED; then
        mv "$INDEX_TMP" "$INDEX_PATH"
        ANY_CHANGE=true
        log "✅ index.json 已更新（全量 $SUB_TOTAL 条）"
    else
        rm -f "$INDEX_TMP"
        log "ℹ index.json 内容未变化"
    fi

    log "📋 字幕: $SUB_TOTAL 个有效，$SUB_CHANGED 个有变化，$SUB_UNCHANGED 个未变化，$SUB_REJECTED 个拒绝"
fi

if ! $ANY_CHANGE; then
    log "ℹ 无真实变化，跳过提交"
    exit 0
fi

git add data/ subtitles/
if git diff --cached --quiet; then
    log "ℹ git 无变更"
    exit 0
fi

SUMMARY="JSON:${JSON_CHANGED} 字幕:${SUB_CHANGED} 索引:${SUB_TOTAL}"
git commit -m "同步 $TARGET_DATE ($SUMMARY)" 2>&1 | tee -a "$LOG_FILE"

for attempt in 1 2 3; do
    if git push origin main 2>&1 | tee -a "$LOG_FILE"; then
        log "🎉 推送成功 ($SUMMARY)"
        exit 0
    fi
    log "⚠ 推送失败，第 ${attempt} 次重试"
    sleep 15
done

log "❌ 推送失败（已重试3次）"
exit 1
