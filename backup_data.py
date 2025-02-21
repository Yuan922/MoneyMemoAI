import os
import shutil
from datetime import datetime
import glob
import pandas as pd

def backup_data():
    # 設定備份目錄
    backup_dir = 'backups'
    data_dir = 'data'
    
    # 建立備份目錄（如果不存在）
    os.makedirs(backup_dir, exist_ok=True)
    
    # 取得當前日期作為備份檔案名稱的一部分
    current_date = datetime.now().strftime('%Y%m%d')
    
    # 尋找所有使用者的資料檔案
    data_files = glob.glob(os.path.join(data_dir, 'expenses_*.csv'))
    
    for data_file in data_files:
        # 取得檔案名稱
        filename = os.path.basename(data_file)
        # 建立備份檔案名稱
        backup_filename = f'{os.path.splitext(filename)[0]}_{current_date}.csv'
        backup_path = os.path.join(backup_dir, backup_filename)
        
        try:
            # 複製檔案到備份目錄
            shutil.copy2(data_file, backup_path)
            print(f"已備份 {filename} 到 {backup_filename}")
        except Exception as e:
            print(f"備份 {filename} 時發生錯誤: {str(e)}")

if __name__ == "__main__":
    backup_data() 