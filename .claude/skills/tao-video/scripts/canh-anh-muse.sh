#!/bin/bash
# Canh ảnh Muse/GaBee cho Monitor: mỗi dòng in ra = một lần đánh thức agent.
#   NEW <giờ> <file>        → có ảnh mới, đi lấy kết quả run tương ứng
#   IM-LANG <giây>s         → đã <giây> giây không có ảnh mới: get_run_status mọi run đang chạy,
#                             run nào quá 150s thì stop_run rồi bắn lại
# Vì sao phải có IM-LANG: lượt treo không sinh ảnh → monitor chỉ báo ảnh mới sẽ im lặng mãi,
# agent tưởng "đang chạy" và ngồi chờ (video "Con số trên tường" v1, 12/10/2026: cảnh 17 treo 4 phút
# không ai hay, người dùng phải nhắc).
# Dùng: Monitor(command="bash ~/.claude/skills/tao-video/scripts/canh-anh-muse.sh [han_giay]", timeout_ms=1800000)
# Monitor hết hạn sau 30 phút → nhớ bật lại nếu còn lượt đang chạy.
HAN=${1:-150}
D="$HOME/Library/Application Support/com.beeflow.app/BeeFlowData/resources/images/media"
start=$(date +%s); last=$start; seen=""
while true; do
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    case "$seen" in *"|$f|"*) ;; *) seen="$seen|$f|"; last=$(date +%s); echo "NEW $(date +%H:%M:%S) $(basename "$f")";; esac
  done < <(find "$D" -name 'muse_*' -newermt "@$start" 2>/dev/null)
  now=$(date +%s)
  if [ $((now - last)) -ge "$HAN" ]; then echo "IM-LANG $((now - last))s — kiểm get_run_status các run đang chạy"; last=$now; fi
  sleep 2
done
