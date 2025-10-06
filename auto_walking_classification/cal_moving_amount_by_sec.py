#!/usr/bin/env python3
"""
POSEパラメータから秒ごとの移動量を計算するスクリプト

使用方法:
python cal_moving_amount_by_sec.py <input_pose_file> <output_motion_file> <fps>

引数:
- input_pose_file: POSEパラメータファイル（7列X行）
- output_motion_file: 出力ファイル（秒数,移動量の形式）
- fps: フレームレート
"""

import sys
import math
import os

def read_pose_data(file_path):
    """
    POSEファイルからX,Z成分（0列目=X, 2列目=Z）を読み込む
    
    Args:
        file_path (str): POSEファイルのパス
        
    Returns:
        list: [(x, z), ...] の形式のリスト
    """
    xz_displacements = []
    
    try:
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                    
                # スペース区切りで分割
                values = line.split()
                if len(values) < 2:
                    print(f"[WARNING] Line {line_num}: Insufficient columns, skipping")
                    continue
                    
                try:
                    x = float(values[0])
                    z = float(values[2])
                    xz_displacements.append((x, z))
                except ValueError as e:
                    print(f"[WARNING] Line {line_num}: Invalid numeric values, skipping: {e}")
                    continue
                    
    except FileNotFoundError:
        print(f"[ERROR] File not found: {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Error reading file {file_path}: {e}")
        sys.exit(1)
        
    return xz_displacements

def calculate_frame_motion(xz_displacements):
    """
    フレーム間の移動量を計算（√(X²+Z²)）
    
    Args:
        xz_displacements (list): [(x, z), ...] の形式のリスト
        
    Returns:
        list: フレーム間の移動量のリスト
    """
    frame_motions = []
    
    for i in range(1, len(xz_displacements)):
        prev_x, prev_z = xz_displacements[i-1]
        curr_x, curr_z = xz_displacements[i]
        
        # フレーム間の変位を計算（X, Z）
        dx = curr_x - prev_x
        dz = curr_z - prev_z
        
        # 移動量を計算（√(X²+Z²)）
        motion = math.sqrt(dx*dx + dz*dz)
        frame_motions.append(motion)
        
    return frame_motions

def aggregate_by_second(frame_motions, fps, start_second=0):
    """
    FPSに基づいて秒ごとの移動量を累積
    
    Args:
        frame_motions (list): フレーム間の移動量のリスト
        fps (float): フレームレート
        start_second (int): 開始秒数（デフォルト: 0）
        
    Returns:
        list: [(秒数, 移動量), ...] の形式のリスト
    """
    per_second_motions = []
    
    # フレーム数をFPSで割って秒数を計算
    total_seconds = math.ceil(len(frame_motions) / fps)
    
    for second in range(total_seconds):
        start_frame = int(second * fps)
        end_frame = int((second + 1) * fps)
        
        # その秒に含まれるフレームの移動量を累積
        motion_sum = 0.0
        frame_count = 0
        
        for frame_idx in range(start_frame, min(end_frame, len(frame_motions))):
            motion_sum += frame_motions[frame_idx]
            frame_count += 1
            
        # 開始秒数を加算して絶対秒数に変換
        absolute_second = start_second + second
        per_second_motions.append((absolute_second, motion_sum))
        
    return per_second_motions

def save_motion_data(per_second_motions, output_file):
    """
    秒ごとの移動量をファイルに保存
    
    Args:
        per_second_motions (list): [(秒数, 移動量), ...] の形式のリスト
        output_file (str): 出力ファイルのパス
    """
    try:
        # 出力ディレクトリが存在しない場合は作成
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        with open(output_file, 'w') as f:
            # ヘッダー行を追加
            f.write("second,motion_amount\n")
            
            for second, motion in per_second_motions:
                f.write(f"{second},{motion:.6f}\n")
                
        print(f"[INFO] Saved motion data to: {output_file}")
        
    except Exception as e:
        print(f"[ERROR] Error saving file {output_file}: {e}")
        sys.exit(1)

def extract_start_second_from_filename(output_file):
    """
    出力ファイル名から開始秒数を抽出する
    
    Args:
        output_file (str): 出力ファイル名（例: "0-14sec.txt"）
        
    Returns:
        int: 開始秒数
    """
    import re
    
    # ファイル名から時間範囲を抽出（例: "0-14sec.txt" -> "0-14"）
    filename = os.path.basename(output_file)
    match = re.search(r'(\d+)-(\d+)sec\.txt', filename)
    
    if match:
        start_sec = int(match.group(1))
        return start_sec
    else:
        print(f"[WARNING] Could not extract start second from filename: {filename}, using 0")
        return 0

def main():
    if len(sys.argv) != 4:
        print("Usage: python cal_moving_amount_by_sec.py <input_pose_file> <output_motion_file> <fps>")
        sys.exit(1)
        
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    try:
        fps = float(sys.argv[3])
        if fps <= 0:
            raise ValueError("FPS must be positive")
    except ValueError as e:
        print(f"[ERROR] Invalid FPS value: {e}")
        sys.exit(1)
        
    # 出力ファイル名から開始秒数を抽出
    start_second = extract_start_second_from_filename(output_file)
        
    print(f"[INFO] Processing: {input_file}")
    print(f"[INFO] Output: {output_file}")
    print(f"[INFO] FPS: {fps}")
    print(f"[INFO] Start second: {start_second}")
    
    # ステップ1: POSEファイルから最初2列（X,Y変位）を読み込み
    print("[INFO] Step 1: Reading pose data...")
    xy_displacements = read_pose_data(input_file)
    print(f"[INFO] Read {len(xy_displacements)} pose data points")
    
    if len(xy_displacements) < 2:
        print("[ERROR] Insufficient pose data (need at least 2 points)")
        sys.exit(1)
        
    # ステップ2-1: フレーム間の移動量を計算
    print("[INFO] Step 2-1: Calculating frame-to-frame motion...")
    frame_motions = calculate_frame_motion(xy_displacements)
    print(f"[INFO] Calculated {len(frame_motions)} frame motions")
    
    # ステップ2-2: 秒ごとの移動量を累積
    print("[INFO] Step 2-2: Aggregating motion by second...")
    per_second_motions = aggregate_by_second(frame_motions, fps, start_second)
    print(f"[INFO] Calculated motion for {len(per_second_motions)} seconds")
    
    # ステップ3: 結果をファイルに保存
    print("[INFO] Step 3: Saving results...")
    save_motion_data(per_second_motions, output_file)
    
    print("[INFO] Processing completed successfully")

if __name__ == "__main__":
    main()
