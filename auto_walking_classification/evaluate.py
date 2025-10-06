#!/usr/bin/env python3
"""
正解データと歩行分類結果を精度比較するスクリプト

使用方法:
python evaluate.py <video_name> <motion_per_sec_dir> <class_result_dir> <walking_threshold1> <walking_threshold2> <annotation_dir>

引数:
- video_name: 動画名
- motion_per_sec_dir: 秒ごとの移動量データディレクトリ
- class_result_dir: 分類結果の保存ディレクトリ
- walking_threshold1: WALKING判定のしきい値
- walking_threshold2: HOLD判定のしきい値
- annotation_dir: 正解データディレクトリ
"""

import sys
import os
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm



def read_annotation_data(annotation_dir, video_name):
    """
    正解データを読み込む
    
    Args:
        annotation_dir (str): 正解データディレクトリ
        video_name (str): 動画名
        
    Returns:
        list: 正解データのリスト（1: 歩行, 0: 静止）
    """
    annotation_file = os.path.join(annotation_dir, f"{video_name}.txt")
    
    if not os.path.exists(annotation_file):
        print(f"[ERROR] Annotation file not found: {annotation_file}")
        sys.exit(1)
    
    annotation_data = []
    
    try:
        with open(annotation_file, 'r') as f:
            # カンマ区切りで読み込み
            content = f.read().strip()
            if content:
                values = content.split(',')
                for value in values:
                    try:
                        annotation_data.append(int(value.strip()))
                    except ValueError:
                        print(f"[WARNING] Invalid annotation value: {value}")
                        continue
            else:
                print(f"[ERROR] Empty annotation file: {annotation_file}")
                sys.exit(1)
                
    except Exception as e:
        print(f"[ERROR] Error reading annotation file {annotation_file}: {e}")
        sys.exit(1)
    
    return annotation_data

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
            reader = csv.reader(f, delimiter=',')
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

def classify_motion(sec_to_motion, threshold):
    """
    移動量に基づいて歩行状態を分類（2クラス: 移動/静止）
    
    Args:
        sec_to_motion (dict): {秒数: 移動量} の辞書
        threshold (float): 分類しきい値
        
    Returns:
        dict: {秒数: 分類結果} の辞書（1: 移動, 0: 静止）
    """
    sec_to_classification = {}
    
    for sec, motion in sec_to_motion.items():
        if motion >= threshold:
            sec_to_classification[sec] = 1  # 移動
        else:
            sec_to_classification[sec] = 0  # 静止
    
    return sec_to_classification

def align_data(annotation_data, sec_to_classification):
    """
    正解データと分類結果を秒数で揃える
    
    Args:
        annotation_data (list): 正解データのリスト
        sec_to_classification (dict): {秒数: 分類結果} の辞書
        
    Returns:
        tuple: (正解データ, 分類結果) のリスト
    """
    aligned_annotation = []
    aligned_classification = []
    
    # 正解データの長さに合わせて処理
    for sec in range(len(annotation_data)):
        if sec in sec_to_classification:
            aligned_annotation.append(annotation_data[sec])
            aligned_classification.append(sec_to_classification[sec])
        else:
            # 分類結果がない場合は静止として扱う
            aligned_annotation.append(annotation_data[sec])
            aligned_classification.append(0)
    
    return aligned_annotation, aligned_classification

def calculate_confusion_matrix(y_true, y_pred):
    """
    混同行列を計算
    
    Args:
        y_true (list): 正解データ
        y_pred (list): 予測結果
        
    Returns:
        numpy.ndarray: 混同行列 [[TN, FP], [FN, TP]]
    """
    tn = fp = fn = tp = 0
    
    for true_val, pred_val in zip(y_true, y_pred):
        if true_val == 0 and pred_val == 0:
            tn += 1  # True Negative
        elif true_val == 0 and pred_val == 1:
            fp += 1  # False Positive
        elif true_val == 1 and pred_val == 0:
            fn += 1  # False Negative
        elif true_val == 1 and pred_val == 1:
            tp += 1  # True Positive
    
    return np.array([[tn, fp], [fn, tp]])

def create_confusion_matrix_plot(y_true, y_pred, threshold, class_result_dir, video_name, threshold_name):
    """
    混同行列を作成して保存
    
    Args:
        y_true (list): 正解データ
        y_pred (list): 予測結果
        threshold (float): 使用したしきい値
        class_result_dir (str): 出力ディレクトリ
        video_name (str): 動画名
        threshold_name (str): しきい値の名前
    """
    # 混同行列を計算
    cm = calculate_confusion_matrix(y_true, y_pred)
    
    # 混同行列のプロット
    plt.figure(figsize=(8, 6))
    
    # ヒートマップを手動で作成
    im = plt.imshow(cm, interpolation='nearest', cmap='Blues')
    plt.colorbar(im)
    
    # ラベルを設定
    classes = ['Stay', 'Walk']
    tick_marks = np.arange(len(classes))
    plt.xticks(tick_marks, classes)
    plt.yticks(tick_marks, classes)
    
    # 値をプロット
    thresh = cm.max() / 2.
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            plt.text(j, i, format(cm[i, j], 'd'),
                    ha="center", va="center",
                    color="white" if cm[i, j] > thresh else "black")
    
    plt.title(f'Confusion Matrix - {video_name} (Threshold: {threshold_name}={threshold})')
    plt.xlabel('Estimated Walk Classification result')
    plt.ylabel('Ground Truth')
    
    # ファイル名を設定
    output_filename = f"{video_name}_confusion_matrix_{threshold_name}.png"
    output_path = os.path.join(class_result_dir, output_filename)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    plt.close()
    
    print(f"[INFO] Saved confusion matrix: {output_filename}")
    
    return cm

def calculate_metrics(y_true, y_pred):
    """
    評価指標を計算
    
    Args:
        y_true (list): 正解データ
        y_pred (list): 予測結果
        
    Returns:
        dict: 評価指標の辞書
    """
    cm = calculate_confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm[0,0], cm[0,1], cm[1,0], cm[1,1]
    
    # 精度 (Accuracy)
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0
    
    # 静止クラスの指標
    static_precision = tn / (tn + fn) if (tn + fn) > 0 else 0
    static_recall = tn / (tn + fp) if (tn + fp) > 0 else 0
    static_f1 = 2 * static_precision * static_recall / (static_precision + static_recall) if (static_precision + static_recall) > 0 else 0
    static_support = tn + fp
    
    # 移動クラスの指標
    motion_precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    motion_recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    motion_f1 = 2 * motion_precision * motion_recall / (motion_precision + motion_recall) if (motion_precision + motion_recall) > 0 else 0
    motion_support = tp + fn
    
    # 平均指標
    macro_precision = (static_precision + motion_precision) / 2
    macro_recall = (static_recall + motion_recall) / 2
    macro_f1 = (static_f1 + motion_f1) / 2
    total_support = static_support + motion_support
    
    # 重み付き平均指標
    weighted_precision = (static_precision * static_support + motion_precision * motion_support) / total_support if total_support > 0 else 0
    weighted_recall = (static_recall * static_support + motion_recall * motion_support) / total_support if total_support > 0 else 0
    weighted_f1 = (static_f1 * static_support + motion_f1 * motion_support) / total_support if total_support > 0 else 0
    
    return {
        'accuracy': accuracy,
        'static': {
            'precision': static_precision,
            'recall': static_recall,
            'f1': static_f1,
            'support': static_support
        },
        'motion': {
            'precision': motion_precision,
            'recall': motion_recall,
            'f1': motion_f1,
            'support': motion_support
        },
        'macro_avg': {
            'precision': macro_precision,
            'recall': macro_recall,
            'f1': macro_f1,
            'support': total_support
        },
        'weighted_avg': {
            'precision': weighted_precision,
            'recall': weighted_recall,
            'f1': weighted_f1,
            'support': total_support
        }
    }

def save_evaluation_report(y_true, y_pred, threshold, class_result_dir, video_name, threshold_name):
    """
    評価レポートを保存
    
    Args:
        y_true (list): 正解データ
        y_pred (list): 予測結果
        threshold (float): 使用したしきい値
        class_result_dir (str): 出力ディレクトリ
        video_name (str): 動画名
        threshold_name (str): しきい値の名前
    """
    # 評価指標を計算
    metrics = calculate_metrics(y_true, y_pred)
    
    # 混同行列を計算
    cm = calculate_confusion_matrix(y_true, y_pred)
    
    # レポートファイルを保存
    report_filename = f"{video_name}_evaluation_report_{threshold_name}.txt"
    report_path = os.path.join(class_result_dir, report_filename)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"歩行分類評価レポート - {video_name}\n")
        f.write("=" * 50 + "\n")
        f.write(f"使用しきい値: {threshold_name} = {threshold}\n")
        f.write(f"総データ数: {len(y_true)}\n")
        f.write(f"精度 (Accuracy): {metrics['accuracy']:.4f}\n\n")
        
        f.write("混同行列:\n")
        f.write(f"          予測\n")
        f.write(f"正解    静止  移動\n")
        f.write(f"静止    {cm[0,0]:4d} {cm[0,1]:4d}\n")
        f.write(f"移動    {cm[1,0]:4d} {cm[1,1]:4d}\n\n")
        
        f.write("詳細分類レポート:\n")
        f.write(f"クラス    精度    再現率   F1スコア  サポート\n")
        f.write(f"静止    {metrics['static']['precision']:.4f}  {metrics['static']['recall']:.4f}  {metrics['static']['f1']:.4f}  {metrics['static']['support']:4d}\n")
        f.write(f"移動    {metrics['motion']['precision']:.4f}  {metrics['motion']['recall']:.4f}  {metrics['motion']['f1']:.4f}  {metrics['motion']['support']:4d}\n")
        f.write(f"平均    {metrics['macro_avg']['precision']:.4f}  {metrics['macro_avg']['recall']:.4f}  {metrics['macro_avg']['f1']:.4f}  {metrics['macro_avg']['support']:4d}\n")
        f.write(f"重み付き平均 {metrics['weighted_avg']['precision']:.4f}  {metrics['weighted_avg']['recall']:.4f}  {metrics['weighted_avg']['f1']:.4f}  {metrics['weighted_avg']['support']:4d}\n")
    
    print(f"[INFO] Saved evaluation report: {report_filename}")
    
    return metrics['accuracy'], metrics

def main():
    if len(sys.argv) != 7:
        print("Usage: python evaluate.py <video_name> <motion_per_sec_dir> <class_result_dir> <walking_threshold1> <walking_threshold2> <annotation_dir>")
        sys.exit(1)
        
    video_name = sys.argv[1]
    motion_per_sec_dir = sys.argv[2]
    class_result_dir = sys.argv[3]
    walking_threshold1 = float(sys.argv[4])
    walking_threshold2 = float(sys.argv[5])
    annotation_dir = sys.argv[6]
    
    print(f"[INFO] Video name: {video_name}")
    print(f"[INFO] Motion per sec directory: {motion_per_sec_dir}")
    print(f"[INFO] Class result directory: {class_result_dir}")
    print(f"[INFO] Walking threshold 1: {walking_threshold1}")
    print(f"[INFO] Walking threshold 2: {walking_threshold2}")
    print(f"[INFO] Annotation directory: {annotation_dir}")
    
    # 出力ディレクトリが存在しない場合は作成
    if not os.path.exists(class_result_dir):
        os.makedirs(class_result_dir)
        print(f"[INFO] Created output directory: {class_result_dir}")
    
    # 正解データを読み込み
    print("[INFO] Reading annotation data...")
    annotation_data = read_annotation_data(annotation_dir, video_name)
    print(f"[INFO] Read {len(annotation_data)} annotation data points")
    
    # 移動量データを読み込み
    print("[INFO] Reading motion data...")
    sec_to_motion = read_motion_data(motion_per_sec_dir)
    print(f"[INFO] Read motion data for {len(sec_to_motion)} seconds")
    
    if not sec_to_motion:
        print("[ERROR] No motion data found")
        sys.exit(1)
    
    # 2つのしきい値で評価
    thresholds = [
        (walking_threshold1, "TH1"),
        (walking_threshold2, "TH2")
    ]
    
    for threshold, threshold_name in thresholds:
        print(f"\n[INFO] Evaluating with threshold {threshold_name} = {threshold}")
        
        # 分類結果を生成
        sec_to_classification = classify_motion(sec_to_motion, threshold)
        
        # データを揃える
        y_true, y_pred = align_data(annotation_data, sec_to_classification)
        
        # 混同行列を作成して保存
        cm = create_confusion_matrix_plot(y_true, y_pred, threshold, class_result_dir, video_name, threshold_name)
        
        # 評価レポートを保存
        accuracy, report = save_evaluation_report(y_true, y_pred, threshold, class_result_dir, video_name, threshold_name)
        
        print(f"[INFO] Accuracy with {threshold_name}: {accuracy:.4f}")
    
    print("[INFO] Evaluation completed successfully")

if __name__ == "__main__":
    main()
