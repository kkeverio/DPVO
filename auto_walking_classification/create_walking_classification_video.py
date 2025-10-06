#!/usr/bin/env python3
"""
しきい値に基づく歩行分類を行い、結果を動画に描画して保存するスクリプト

使用方法:
python create_walking_classification_video.py <video_path> <motion_per_sec_dir> <class_result_dir> <fps> <slam_duration_sec> <walking_threshold1> <walking_threshold2> <video_name>

引数:
- video_path: 元動画ファイルのパス
- motion_per_sec_dir: 秒ごとの移動量データディレクトリ
- class_result_dir: 分類結果動画の保存ディレクトリ
- fps: フレームレート
- slam_duration_sec: SLAMセグメントの長さ（秒）
- walking_threshold1: WALKING判定のしきい値
- walking_threshold2: HOLD判定のしきい値
- video_name: 動画名
"""

import sys
import os
import csv
from collections import defaultdict
import numpy as np
import cv2

def read_motion_data(motion_per_sec_dir):
    """
    秒ごとの移動量データを読み込む
    
    Args:
        motion_per_sec_dir (str): 秒ごとの移動量データディレクトリ
        
    Returns:
        dict: {秒数: 移動量} の辞書
    """
    sec_to_motion = {}
    segment_files = [f for f in os.listdir(motion_per_sec_dir) if f.endswith('.txt') and 'sec.txt' in f]

    for segment_file in sorted(segment_files):
        segment_path = os.path.join(motion_per_sec_dir, segment_file)
        # ファイル名から時間範囲を取得（例: 0-14sec.txt -> start=0, end=14）
        time_range = segment_file.replace('sec.txt', '')
        start_sec, end_sec = map(int, time_range.split('-'))
        
        with open(segment_path, 'r') as f:
            reader = csv.reader(f, delimiter=',')  # カンマ区切りに変更
            header = next(reader)  # ヘッダー行をスキップ
            for row in reader:
                if not row or len(row) < 2:
                    continue
                try:
                    # 期待フォーマット: 秒数, 移動量
                    sec = int(float(row[0]))
                    motion_amount = float(row[1])
                    sec_to_motion[sec] = motion_amount
                except Exception as e:
                    print(f"[WARNING] Skipping invalid row in {segment_file}: {row}, Error: {e}")
                    continue

    return sec_to_motion

def classify_motion(sec_to_motion, walking_threshold1, walking_threshold2):
    """
    移動量に基づいて歩行状態を分類
    
    Args:
        sec_to_motion (dict): {秒数: 移動量} の辞書
        walking_threshold1 (float): WALKING判定のしきい値
        walking_threshold2 (float): HOLD判定のしきい値
        
    Returns:
        dict: {秒数: (ラベル, 色)} の辞書
    """
    sec_to_label = {}
    max_sec = max(sec_to_motion.keys())
    
    for s in range(0, max_sec + 1):
        mv = sec_to_motion.get(s, 0.0)
        if mv >= walking_threshold1:
            sec_to_label[s] = ("WALKING", (0, 200, 0))  # green
        elif mv >= walking_threshold2:
            sec_to_label[s] = ("HOLD", (0, 200, 200))   # yellow-ish
        else:
            sec_to_label[s] = ("STAYING", (0, 0, 200))  # red-ish (BGR)
    
    return sec_to_label

def create_classification_video(video_path, sec_to_label, class_result_dir, video_name, fps):
    """
    分類結果を動画に描画して保存
    
    Args:
        video_path (str): 元動画ファイルのパス
        sec_to_label (dict): {秒数: (ラベル, 色)} の辞書
        class_result_dir (str): 出力ディレクトリ
        video_name (str): 動画名
        fps (float): フレームレート
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[ERROR] cannot open video: {video_path}")
        sys.exit(1)

    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    orig_fps = cap.get(cv2.CAP_PROP_FPS)
    
    # 描画用fpsは元動画fpsを使用
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_path = os.path.join(class_result_dir, f"{video_name}_classified.mp4")
    writer = cv2.VideoWriter(out_path, fourcc, orig_fps if orig_fps > 0 else fps, (orig_w, orig_h))

    frame_idx = 0
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.8
    thickness = 2

    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # 対応する秒を算出（DPVOの集計と整合性をとるため FPS を使用）
        sec = int(frame_idx / fps)
        label, color = sec_to_label.get(sec, ("STAYING", (0, 0, 200)))
        text = f"{label} (sec {sec})"
        
        # 文字の背景用に半透明矩形を描く
        (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        x0, y0 = 10, 10
        cv2.rectangle(frame, (x0, y0), (x0 + tw + 10, y0 + th + 10), (0, 0, 0), -1)
        cv2.addWeighted(frame[y0:y0+th+10, x0:x0+tw+10], 0.5, frame[y0:y0+th+10, x0:x0+tw+10], 0.5, 0, frame[y0:y0+th+10, x0:x0+tw+10])
        cv2.putText(frame, text, (x0 + 5, y0 + th + 2), font, font_scale, color, thickness, cv2.LINE_AA)

        writer.write(frame)
        frame_idx += 1

    cap.release()
    writer.release()
    print(f"[INFO] Saved classified video: {out_path}")

def save_statistics(sec_to_motion, motion_per_sec_dir, video_name, slam_duration_sec, segment_files):
    """
    統計情報をファイルに保存
    
    Args:
        sec_to_motion (dict): {秒数: 移動量} の辞書
        motion_per_sec_dir (str): 統計ファイルの保存ディレクトリ
        video_name (str): 動画名
        slam_duration_sec (int): SLAMセグメントの長さ
        segment_files (list): セグメントファイルのリスト
    """
    max_sec = max(sec_to_motion.keys())
    
    # 1分ごとの移動量の棒グラフ
    minute_to_sum = defaultdict(float)
    for s, v in sec_to_motion.items():
        minute_to_sum[s // 60] += v
    
    # 統合された統計情報を出力
    stats_file = os.path.join(motion_per_sec_dir, f"{video_name}_integrated_stats.txt")
    with open(stats_file, 'w') as f:
        f.write(f"Integrated Motion Statistics for {video_name}\n")
        f.write("=" * 50 + "\n")
        f.write(f"Total duration: {max_sec + 1} seconds\n")
        f.write(f"Number of segments: {len(segment_files)}\n")
        f.write(f"Segment duration: {slam_duration_sec} seconds\n")
        f.write(f"Total motion: {sum(sec_to_motion.values()):.6f}\n")
        f.write(f"Average motion per second: {np.mean(list(sec_to_motion.values())):.6f}\n")
        f.write(f"Max motion per second: {np.max(list(sec_to_motion.values())):.6f}\n")
        f.write(f"Min motion per second: {np.min(list(sec_to_motion.values())):.6f}\n")
        
        # 1分ごとの統計
        f.write(f"\nPer-minute statistics:\n")
        for m in sorted(minute_to_sum.keys()):
            f.write(f"Minute {m}: {minute_to_sum[m]:.6f}\n")

    print(f"[INFO] Saved integrated statistics: {stats_file}")

def main():
    if len(sys.argv) != 9:
        print("Usage: python create_walking_classification_video.py <video_path> <motion_per_sec_dir> <class_result_dir> <fps> <slam_duration_sec> <walking_threshold1> <walking_threshold2> <video_name>")
        sys.exit(1)
        
    video_path = sys.argv[1]
    motion_per_sec_dir = sys.argv[2]
    class_result_dir = sys.argv[3]
    fps = float(sys.argv[4])
    slam_duration_sec = int(float(sys.argv[5]))
    walking_threshold1 = float(sys.argv[6])
    walking_threshold2 = float(sys.argv[7])
    video_name = sys.argv[8]
    
    print(f"[INFO] Video path: {video_path}")
    print(f"[INFO] Motion per sec directory: {motion_per_sec_dir}")
    print(f"[INFO] Class result directory: {class_result_dir}")
    print(f"[INFO] FPS: {fps}")
    print(f"[INFO] SLAM duration: {slam_duration_sec} seconds")
    print(f"[INFO] Walking threshold 1: {walking_threshold1}")
    print(f"[INFO] Walking threshold 2: {walking_threshold2}")
    print(f"[INFO] Video name: {video_name}")
    
    # 出力ディレクトリが存在しない場合は作成
    if not os.path.exists(class_result_dir):
        os.makedirs(class_result_dir)
        print(f"[INFO] Created output directory: {class_result_dir}")
    
    # 秒ごとの移動量データを読み込み
    print("[INFO] Reading motion data...")
    sec_to_motion = read_motion_data(motion_per_sec_dir)
    
    if not sec_to_motion:
        print(f"[ERROR] No motion data found in {motion_per_sec_dir}")
        sys.exit(1)
    
    max_sec = max(sec_to_motion.keys())
    print(f"[INFO] Integrated motion data: 0-{max_sec} seconds")
    
    # 歩行状態を分類
    print("[INFO] Classifying motion...")
    sec_to_label = classify_motion(sec_to_motion, walking_threshold1, walking_threshold2)
    
    # 分類結果を動画に描画して保存
    print("[INFO] Creating classification video...")
    create_classification_video(video_path, sec_to_label, class_result_dir, video_name, fps)
    
    # 統計情報を保存
    print("[INFO] Saving statistics...")
    segment_files = [f for f in os.listdir(motion_per_sec_dir) if f.endswith('.txt') and 'sec.txt' in f]
    save_statistics(sec_to_motion, motion_per_sec_dir, video_name, slam_duration_sec, segment_files)
    
    print("[INFO] Processing completed successfully")

if __name__ == "__main__":
    main()

