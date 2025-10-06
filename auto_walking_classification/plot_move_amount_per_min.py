#!/usr/bin/env python3
"""
秒ごとの移動量データを1分ごとの棒グラフにプロットするスクリプト

使用方法:
python plot_move_amount_per_min.py <motion_per_sec_dir> <motion_per_min_dir> <video_name>

引数:
- motion_per_sec_dir: 秒ごとの移動量データが保存されているディレクトリ
- motion_per_min_dir: 1分ごとの棒グラフを保存するディレクトリ
- video_name: 動画名（ファイル名に使用）
"""

import sys
import os
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from collections import defaultdict

def read_motion_data(motion_per_sec_dir):
    """
    秒ごとの移動量データを読み込む
    
    Args:
        motion_per_sec_dir (str): 秒ごとの移動量データディレクトリ
        
    Returns:
        dict: {秒数: 移動量} の辞書
    """
    sec_to_motion = {}
    
    # ディレクトリ内のすべてのsec.txtファイルを処理
    for filename in os.listdir(motion_per_sec_dir):
        if filename.endswith('sec.txt'):
            filepath = os.path.join(motion_per_sec_dir, filename)
            
            try:
                with open(filepath, 'r') as f:
                    reader = csv.reader(f, delimiter=',')
                    header = next(reader)  # ヘッダー行をスキップ
                    
                    for row in reader:
                        if not row or len(row) < 2:
                            continue
                            
                        try:
                            sec = int(float(row[0]))
                            motion_amount = float(row[1])
                            sec_to_motion[sec] = motion_amount
                        except (ValueError, IndexError) as e:
                            print(f"[WARNING] Skipping invalid row in {filename}: {row}, Error: {e}")
                            continue
                            
            except Exception as e:
                print(f"[WARNING] Error reading {filename}: {e}")
                continue
                
    return sec_to_motion

def read_annotation_data(annotation_dir, video_name):
    """
    正解データを読み込む
    
    Args:
        annotation_dir (str): 正解データディレクトリ
        video_name (str): 動画名
        
    Returns:
        dict: {秒数: 正解値} の辞書（1: 歩行, 0: 静止）
    """
    annotation_file = os.path.join(annotation_dir, f"{video_name}.txt")
    
    if not os.path.exists(annotation_file):
        print(f"[WARNING] Annotation file not found: {annotation_file}")
        return {}
    
    sec_to_annotation = {}
    
    try:
        with open(annotation_file, 'r') as f:
            # カンマ区切りで読み込み
            content = f.read().strip()
            if content:
                values = content.split(',')
                for sec, value in enumerate(values):
                    try:
                        sec_to_annotation[sec] = int(value.strip())
                    except ValueError:
                        print(f"[WARNING] Invalid annotation value at second {sec}: {value}")
                        continue
            else:
                print(f"[WARNING] Empty annotation file: {annotation_file}")
                return {}
                
    except Exception as e:
        print(f"[WARNING] Error reading annotation file {annotation_file}: {e}")
        return {}
    
    return sec_to_annotation

def classify_motion(sec_to_motion, walking_threshold1, walking_threshold2):
    """
    移動量に基づいて歩行状態を分類
    
    Args:
        sec_to_motion (dict): {秒数: 移動量} の辞書
        walking_threshold1 (float): WALKING判定のしきい値
        walking_threshold2 (float): HOLD判定のしきい値
        
    Returns:
        dict: {秒数: 分類結果} の辞書（'walk', 'hold', 'stay'）
    """
    sec_to_classification = {}
    
    for sec, motion in sec_to_motion.items():
        if motion >= walking_threshold1:
            sec_to_classification[sec] = 'walk'
        elif motion >= walking_threshold2:
            sec_to_classification[sec] = 'hold'
        else:
            sec_to_classification[sec] = 'stay'
    
    return sec_to_classification

def create_minute_plots(sec_to_motion, sec_to_annotation, sec_to_classification, motion_per_min_dir, video_name):
    """
    1分ごとの棒グラフを作成（背景色付き）
    
    Args:
        sec_to_motion (dict): {秒数: 移動量} の辞書
        sec_to_annotation (dict): {秒数: 正解値} の辞書
        sec_to_classification (dict): {秒数: 分類結果} の辞書
        motion_per_min_dir (str): 出力ディレクトリ
        video_name (str): 動画名
    """
    if not sec_to_motion:
        print("[ERROR] No motion data found")
        return
        
    # 最大秒数を取得
    max_sec = max(sec_to_motion.keys())
    total_minutes = (max_sec // 60) + 1
    
    print(f"[INFO] Creating plots for {total_minutes} minutes (0-{max_sec} seconds)")
    
    # 色の定義
    # 正解データ: 1→青色, 0→赤色
    annotation_colors = {1: 'lightblue', 0: 'lightcoral'}
    # 歩行判定結果: walk→青色, hold→黄色, stay→赤色
    classification_colors = {'walk': 'lightblue', 'hold': 'lightyellow', 'stay': 'lightcoral'}
    
    # 各分ごとにプロットを作成
    for minute in range(total_minutes):
        plt.figure(figsize=(14, 8))
        
        # その分の秒ごとの移動量を取得（0-59秒の範囲）
        minute_values = []
        annotation_bg_colors = []
        classification_bg_colors = []
        
        # 0-59秒の範囲で移動量を取得（データがない場合は0）
        for sec in range(60):
            abs_sec = minute * 60 + sec
            if abs_sec in sec_to_motion:
                minute_values.append(sec_to_motion[abs_sec])
            else:
                minute_values.append(0.0)
            
            # 正解データの背景色
            if abs_sec in sec_to_annotation:
                annotation_bg_colors.append(annotation_colors[sec_to_annotation[abs_sec]])
            else:
                annotation_bg_colors.append('white')  # データがない場合は白
            
            # 歩行判定結果の背景色
            if abs_sec in sec_to_classification:
                classification_bg_colors.append(classification_colors[sec_to_classification[abs_sec]])
            else:
                classification_bg_colors.append('white')  # データがない場合は白
        
        # 背景色を設定（各秒ごとの背景）
        max_value = max(minute_values) if minute_values else 1.0
        
        # 正解データの背景（上半分の背景）
        for i, color in enumerate(annotation_bg_colors):
            plt.axvspan(i-0.4, i+0.4, ymin=0.5, ymax=1.0, color=color, alpha=0.3)
        
        # 歩行判定結果の背景（下半分の背景）
        for i, color in enumerate(classification_bg_colors):
            plt.axvspan(i-0.4, i+0.4, ymin=0.0, ymax=0.5, color=color, alpha=0.3)
        
        # 棒グラフを作成（0-59秒の60本の棒）
        plt.bar(range(60), minute_values, width=0.8, color='steelblue', alpha=0.8)
        
        # グラフの設定
        plt.title(f"Motion per Second: {video_name} - Minute {minute} ({minute*60}-{minute*60+59}sec)\n"
                 f"Top half: Ground Truth (Blue=Walk, Red=Stay)\n"
                 f"Bottom half: Classification (Blue=Walk, Yellow=Hold, Red=Stay)", fontsize=10)
        plt.xlabel("Second (0-59)")
        plt.ylabel("Motion Amount (sqrt(x^2+z^2))")
        plt.xticks(range(0, 60, 5), [str(i) for i in range(0, 60, 5)])  # 5秒ごとにラベル
        plt.grid(True, axis='y', alpha=0.3)
        
        # ファイル名を分ごとに設定
        output_filename = f"{video_name}_motion_minute_{minute:02d}_{minute*60}-{minute*60+59}sec.png"
        output_path = os.path.join(motion_per_min_dir, output_filename)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=200, bbox_inches='tight')
        plt.close()
        
        print(f"[INFO] Saved minute {minute} motion plot: {output_filename}")

def main():
    if len(sys.argv) != 7:
        print("Usage: python plot_move_amount_per_min.py <motion_per_sec_dir> <motion_per_min_dir> <video_name> <walking_threshold1> <walking_threshold2> <annotation_dir>")
        sys.exit(1)
        
    motion_per_sec_dir = sys.argv[1]
    motion_per_min_dir = sys.argv[2]
    video_name = sys.argv[3]
    walking_threshold1 = float(sys.argv[4])
    walking_threshold2 = float(sys.argv[5])
    annotation_dir = sys.argv[6]
    
    print(f"[INFO] Motion per sec directory: {motion_per_sec_dir}")
    print(f"[INFO] Motion per min directory: {motion_per_min_dir}")
    print(f"[INFO] Video name: {video_name}")
    print(f"[INFO] Walking threshold 1: {walking_threshold1}")
    print(f"[INFO] Walking threshold 2: {walking_threshold2}")
    print(f"[INFO] Annotation directory: {annotation_dir}")
    
    # 出力ディレクトリが存在しない場合は作成
    if not os.path.exists(motion_per_min_dir):
        os.makedirs(motion_per_min_dir)
        print(f"[INFO] Created output directory: {motion_per_min_dir}")
    
    # 秒ごとの移動量データを読み込み
    print("[INFO] Reading motion data...")
    sec_to_motion = read_motion_data(motion_per_sec_dir)
    
    if not sec_to_motion:
        print("[ERROR] No motion data found")
        sys.exit(1)
        
    print(f"[INFO] Read motion data for {len(sec_to_motion)} seconds")
    
    # 正解データを読み込み
    print("[INFO] Reading annotation data...")
    sec_to_annotation = read_annotation_data(annotation_dir, video_name)
    print(f"[INFO] Read annotation data for {len(sec_to_annotation)} seconds")
    
    # 歩行判定結果を生成
    print("[INFO] Classifying motion...")
    sec_to_classification = classify_motion(sec_to_motion, walking_threshold1, walking_threshold2)
    print(f"[INFO] Generated classification for {len(sec_to_classification)} seconds")
    
    # 1分ごとの棒グラフを作成
    print("[INFO] Creating minute-by-minute plots...")
    create_minute_plots(sec_to_motion, sec_to_annotation, sec_to_classification, motion_per_min_dir, video_name)
    
    print("[INFO] Plot creation completed successfully")

if __name__ == "__main__":
    main()
