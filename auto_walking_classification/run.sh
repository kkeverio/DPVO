#!/usr/bin/env bash
set -euo pipefail

# =============================
# step1 パス,変数の設定
# =============================

# 入力動画ディレクトリ
INPUT_VIDEO_DIR="/media/kakerukoizumi/ykk/DPVO_SLAM/input_video"
# 出力結果保存ディレクトリ（動画ごとのサブディレクトリを作成）
RESULT_BASE_DIR="/media/kakerukoizumi/ykk/DPVO_SLAM/result"

# DPVO 実行に必要な設定
REPO_ROOT="/home/kakerukoizumi/research/DPVO"
CALIB_FILE="${REPO_ROOT}/calib/vid_010_re.txt"   # 必要に応じて変更
NETWORK_WEIGHTS="${REPO_ROOT}/dpvo.pth"            # 必要に応じて変更
CONFIG_FILE="${REPO_ROOT}/config/default.yaml"

# 実行パラメータ（必要に応じて上書き可能）
FPS="${FPS:-30}"                       # fps = 30 (default)
SLAM_DURATION_SEC="${SLAM_DURATION_SEC:-15}"  # 一回のスラム実行時間 = 15 sec (default)
WALKING_THRESHOLD1="${WALKING_THRESHOLD1:-1.5}"
WALKING_THRESHOLD2="${WALKING_THRESHOLD2:-1.0}"
# キャリブレーションファイル名（拡張子なし）を指定。デフォルト ykk
CALIB_NAME="${CALIB_NAME:-ykk}"
# キャリブレーションパスを確定
CALIB_FILE="${REPO_ROOT}/calib/${CALIB_NAME}.txt"

# サポートする動画拡張子
VIDEO_EXTS=(mp4 MP4 mov MOV avi AVI mkv MKV)

# 事前チェック
if [[ ! -d "$INPUT_VIDEO_DIR" ]]; then
  echo "[ERROR] INPUT_VIDEO_DIR not found: $INPUT_VIDEO_DIR" >&2
  exit 1
fi
mkdir -p "$RESULT_BASE_DIR"

if [[ ! -f "$CALIB_FILE" ]]; then
  echo "[ERROR] CALIB_FILE not found: $CALIB_FILE" >&2
  echo "Please set CALIB_FILE in run.sh to a valid calibration file." >&2
  exit 1
fi
if [[ ! -f "$NETWORK_WEIGHTS" ]]; then
  echo "[ERROR] NETWORK_WEIGHTS not found: $NETWORK_WEIGHTS" >&2
  echo "Please set NETWORK_WEIGHTS in run.sh to your dpvo.pth." >&2
  exit 1
fi
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "[ERROR] CONFIG_FILE not found: $CONFIG_FILE" >&2
  exit 1
fi

# FFmpegが利用可能かチェック
if ! command -v ffmpeg &> /dev/null; then
  echo "[ERROR] ffmpeg is not installed. Please install ffmpeg first." >&2
  exit 1
fi

# =============================
# step2 動画分割とSLAM実行
# =============================

shopt -s nullglob

for ext in "${VIDEO_EXTS[@]}"; do
  for VIDEO_PATH in "$INPUT_VIDEO_DIR"/*."$ext"; do
    [[ -e "$VIDEO_PATH" ]] || continue

    VIDEO_FILE="$(basename -- "$VIDEO_PATH")"
    VIDEO_NAME="${VIDEO_FILE%.*}"
    ORIGINAL_VIDEO_NAME="${VIDEO_NAME}"  # 元の動画名を保持

    # 動画ごとの出力ディレクトリ（FPSとSLAM_DURATIONとCALIB_NAMEを含む）
    OUT_DIR="${RESULT_BASE_DIR}/${VIDEO_NAME}_fps${FPS}_dur${SLAM_DURATION_SEC}_calib${CALIB_NAME}"
    MOTION_PER_SLAM_DIR="${OUT_DIR}/motion_amount_for_each_slam"
    MOTION_PER_SEC_DIR="${OUT_DIR}/motion_amount_for_sec"
    MOTION_PER_MIN_DIR="${OUT_DIR}/motion_amount_for_1_min"
    CLASS_RESULT_DIR="${OUT_DIR}/walking_classificaton_result"
    TEMP_VIDEO_DIR="${OUT_DIR}/temp_video_segments"
    mkdir -p "$MOTION_PER_SLAM_DIR" "$MOTION_PER_SEC_DIR" "$MOTION_PER_MIN_DIR" "$CLASS_RESULT_DIR" "$TEMP_VIDEO_DIR"

    echo "[INFO] Processing video: $VIDEO_FILE"

    # 動画の長さを取得（秒単位）
    VIDEO_DURATION=$(ffprobe -v quiet -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$VIDEO_PATH" 2>/dev/null | cut -d. -f1)
    if [[ -z "$VIDEO_DURATION" ]] || [[ "$VIDEO_DURATION" -eq 0 ]]; then
      echo "[ERROR] Could not determine video duration for: $VIDEO_FILE" >&2
      continue
    fi
    echo "[INFO] Video duration: ${VIDEO_DURATION} seconds"

    # 既存の一時ファイルをクリア
    rm -f "$TEMP_VIDEO_DIR"/*.mp4

    # 動画を15秒ごとに分割
    echo "[INFO] Splitting video into ${SLAM_DURATION_SEC}-second segments..."
    ffmpeg -i "$VIDEO_PATH" \
      -an \
      -r "$FPS" \
      -c:v libx264 -pix_fmt yuv420p -preset veryfast -crf 18 \
      -g "$FPS" -keyint_min "$FPS" -sc_threshold 0 \
      -force_key_frames "expr:gte(t,n_forced*${SLAM_DURATION_SEC})" \
      -segment_time "$SLAM_DURATION_SEC" -reset_timestamps 1 \
      -f segment "$TEMP_VIDEO_DIR/segment_%03d.mp4" -y 2>/dev/null

    # 分割されたファイルの数を確認
    SEGMENT_FILES=("$TEMP_VIDEO_DIR"/segment_*.mp4)
    if [[ ${#SEGMENT_FILES[@]} -eq 0 ]]; then
      echo "[ERROR] No video segments were created" >&2
      continue
    fi
    echo "[INFO] Created ${#SEGMENT_FILES[@]} video segments"

    # 各分割動画に対してSLAM実行
    for i in "${!SEGMENT_FILES[@]}"; do
      SEGMENT_FILE="${SEGMENT_FILES[$i]}"
      START_TIME=$((i * SLAM_DURATION_SEC))
      END_TIME=$((START_TIME + SLAM_DURATION_SEC - 1))
      
      # 動画の長さを超える場合は調整
      if [[ $END_TIME -ge $VIDEO_DURATION ]]; then
        END_TIME=$((VIDEO_DURATION - 1))
      fi
      
      SEGMENT_NAME="${ORIGINAL_VIDEO_NAME}_${START_TIME}-${END_TIME}sec"
      echo "[INFO] Processing segment: ${START_TIME}-${END_TIME}sec"

      # demo.py 実行（分割された動画に対して）
      pushd "$REPO_ROOT" >/dev/null
      python demo.py \
        --imagedir "$SEGMENT_FILE" \
        --calib "$CALIB_FILE" \
        --name "$SEGMENT_NAME" \
        --stride 1 \
        --plot

      popd >/dev/null


      # 分割動画の結果をmotion_amount_for_each_slamにコピー
      cp "/home/kakerukoizumi/research/DPVO/auto_walking_classification/tmp_result/poses.txt" "$MOTION_PER_SLAM_DIR/${START_TIME}-${END_TIME}sec.txt"
      echo "[INFO] Saved motion data: ${START_TIME}-${END_TIME}sec.txt"
      
      # cal_moving_amount_by_sec.pyを実行して秒ごとの移動量を計算
      echo "[INFO] Calculating per-second motion data..."
      python "$REPO_ROOT/auto_walking_classification/cal_moving_amount_by_sec.py" \
        "$MOTION_PER_SLAM_DIR/${START_TIME}-${END_TIME}sec.txt" \
        "$MOTION_PER_SEC_DIR/${START_TIME}-${END_TIME}sec.txt" \
        "$FPS"
      echo "[INFO] Saved per-second motion data: ${START_TIME}-${END_TIME}sec.txt"
    done

    # =============================
    # step3 1分ごとの移動量のグラフプロット＆保存
    # 全セグメントの結果を統合して1分棒グラフ/分類動画を作成
    # =============================

    # 1分ごとの棒グラフを作成
    echo "[INFO] Creating minute-by-minute motion plots..."
    python "$REPO_ROOT/auto_walking_classification/plot_move_amount_per_min.py" \
      "$MOTION_PER_SEC_DIR" \
      "$MOTION_PER_MIN_DIR" \
      "$ORIGINAL_VIDEO_NAME" \
      "$WALKING_THRESHOLD1" \
      "$WALKING_THRESHOLD2" \
      "$REPO_ROOT/auto_walking_classification/anotation_for_walk_classification"
    echo "[INFO] Completed minute-by-minute motion plots"

    # 歩行分類動画と統計を作成
    echo "[INFO] Creating walking classification video..."
    python "$REPO_ROOT/auto_walking_classification/create_walking_classification_video.py" \
      "$VIDEO_PATH" \
      "$MOTION_PER_SEC_DIR" \
      "$CLASS_RESULT_DIR" \
      "$FPS" \
      "$SLAM_DURATION_SEC" \
      "$WALKING_THRESHOLD1" \
      "$WALKING_THRESHOLD2" \
      "$ORIGINAL_VIDEO_NAME"
    echo "[INFO] Completed walking classification video"

    # 正解データと歩行分類結果を精度比較
    echo "[INFO] Evaluating classification accuracy..."
    python "$REPO_ROOT/auto_walking_classification/evaluate.py" \
      "$ORIGINAL_VIDEO_NAME" \
      "$MOTION_PER_SEC_DIR" \
      "$CLASS_RESULT_DIR" \
      "$WALKING_THRESHOLD1" \
      "$WALKING_THRESHOLD2" \
      "$REPO_ROOT/auto_walking_classification/anotation_for_walk_classification"
    echo "[INFO] Completed evaluation"

    # 一時ファイルのクリーンアップ
    rm -rf "$TEMP_VIDEO_DIR"
    
    echo "[INFO] Finished: $VIDEO_FILE"
  done
done

echo "[INFO] All done."