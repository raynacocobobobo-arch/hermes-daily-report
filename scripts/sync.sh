#!/bin/bash
# Hermes Daily Report — 自动同步脚本
# 每天 22:00 由 cron 触发
# 将当日研报 JSON 复制到仓库 → git push → GitHub 私有仓库

set -euo pipefail

REPO_DIR="/home/ubuntu/projects/hermes-daily-report"
SOURCE_DIR="/home/ubuntu/Desktop/hermes/研报"
SSH_KEY="/home/ubuntu/.ssh/hermes_daily_report_ed25519"
TODAY=$(date +%Y-%m-%d)
LOG_FILE="$REPO_DIR/scripts/sync.log"

# 限制日志行数
tail -n 200 "$LOG_FILE" 2>/dev/null > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE" || true

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "========== 同步开始 =========="

# 1. 拉取最新
cd "$REPO_DIR"
export GIT_SSH_COMMAND="ssh -i $SSH_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes"
git pull origin main 2>&1 | tee -a "$LOG_FILE" || log "⚠ pull失败（可能首次推送）"

# 2. 复制当日研报 JSON
COPIED=0
for f in "$SOURCE_DIR/$TODAY"*.json; do
    if [ -f "$f" ]; then
        cp "$f" "$REPO_DIR/data/"
        log "✅ 复制: $(basename "$f")"
        COPIED=$((COPIED + 1))
    fi
done

if [ "$COPIED" -eq 0 ]; then
    log "⚠ 未找到当日研报 JSON ($TODAY)"
    exit 0
fi

# 3. 提交
cd "$REPO_DIR"
git add data/
if git diff --cached --quiet; then
    log "ℹ 无变更，跳过提交"
    exit 0
fi

git commit -m "研报同步 $TODAY ($COPIED 文件)" 2>&1 | tee -a "$LOG_FILE"

# 4. 推送（最多重试3次）
for i in 1 2 3; do
    if git push origin main 2>&1 | tee -a "$LOG_FILE"; then
        log "🎉 推送成功"
        exit 0
    fi
    log "⚠ 推送失败，第${i}次重试..."
    sleep 15
done

log "❌ 推送失败（已重试3次）"
exit 1