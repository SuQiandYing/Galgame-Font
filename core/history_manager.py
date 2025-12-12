import os
import shutil
import json
import tempfile
from datetime import datetime
from collections import deque

class HistoryManager:
    def __init__(self, max_history=20):
        self.max_history = max_history
        self.history = deque(maxlen=max_history)
        self.redo_stack = deque(maxlen=max_history)
        self.temp_dir = os.path.join(tempfile.gettempdir(), "gal_font_tool_history")
        os.makedirs(self.temp_dir, exist_ok=True)
        
    def record(self, action_name, file_path, description=""):
        if not os.path.exists(file_path):
            return False
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_name = f"{timestamp}_{os.path.basename(file_path)}"
        backup_path = os.path.join(self.temp_dir, backup_name)
        
        try:
            shutil.copy2(file_path, backup_path)
            
            record = {
                'action': action_name,
                'original_path': file_path,
                'backup_path': backup_path,
                'timestamp': timestamp,
                'description': description,
                'time_str': datetime.now().strftime("%H:%M:%S"),
                'is_new_file': False
            }
            
            self.history.append(record)
            self.redo_stack.clear()
            return True
            
        except Exception as e:
            print(f"History record failed: {e}")
            return False
    
    def record_before_overwrite(self, action_name, file_path, description=""):
        if not os.path.exists(file_path):
            return False
        return self.record(action_name, file_path, description + " [覆盖前]")
    
    def record_new_file(self, action_name, file_path, description=""):
        if not os.path.exists(file_path):
            return False
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        record = {
            'action': action_name,
            'original_path': file_path,
            'backup_path': None,
            'timestamp': timestamp,
            'description': description,
            'time_str': datetime.now().strftime("%H:%M:%S"),
            'is_new_file': True
        }
        
        self.history.append(record)
        self.redo_stack.clear()
        return True
    
    def undo(self):
        if not self.history:
            return None, "没有可撤销的操作"
        
        record = self.history.pop()
        
        if record.get('is_new_file', False):
            try:
                if os.path.exists(record['original_path']):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    backup_name = f"redo_{timestamp}_{os.path.basename(record['original_path'])}"
                    backup_path = os.path.join(self.temp_dir, backup_name)
                    shutil.copy2(record['original_path'], backup_path)
                    os.remove(record['original_path'])
                    
                    redo_record = record.copy()
                    redo_record['backup_path'] = backup_path
                    self.redo_stack.append(redo_record)
                    
                    return record, f"已撤销: {record['action']} (删除新文件)"
            except Exception as e:
                return None, f"撤销失败: {e}"
        
        if not record['backup_path'] or not os.path.exists(record['backup_path']):
            return None, "备份文件已丢失"
        
        try:
            current_backup = None
            if os.path.exists(record['original_path']):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                current_backup_name = f"redo_{timestamp}_{os.path.basename(record['original_path'])}"
                current_backup = os.path.join(self.temp_dir, current_backup_name)
                shutil.copy2(record['original_path'], current_backup)
            
            shutil.copy2(record['backup_path'], record['original_path'])
            
            redo_record = record.copy()
            if current_backup:
                redo_record['backup_path'] = current_backup
            self.redo_stack.append(redo_record)
            
            return record, f"已撤销: {record['action']}"
            
        except Exception as e:
            return None, f"撤销失败: {e}"
    
    def redo(self):
        if not self.redo_stack:
            return None, "没有可重做的操作"
        
        record = self.redo_stack.pop()
        
        if record.get('is_new_file', False):
            if record['backup_path'] and os.path.exists(record['backup_path']):
                try:
                    shutil.copy2(record['backup_path'], record['original_path'])
                    
                    undo_record = record.copy()
                    undo_record['backup_path'] = None
                    self.history.append(undo_record)
                    
                    return record, f"已重做: {record['action']}"
                except Exception as e:
                    return None, f"重做失败: {e}"
            else:
                return None, "重做文件已丢失"
        
        if not record['backup_path'] or not os.path.exists(record['backup_path']):
            return None, "重做文件已丢失"
        
        try:
            if os.path.exists(record['original_path']):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                undo_backup_name = f"{timestamp}_{os.path.basename(record['original_path'])}"
                undo_backup = os.path.join(self.temp_dir, undo_backup_name)
                shutil.copy2(record['original_path'], undo_backup)
                
                undo_record = record.copy()
                undo_record['backup_path'] = undo_backup
                self.history.append(undo_record)
            
            shutil.copy2(record['backup_path'], record['original_path'])
            
            return record, f"已重做: {record['action']}"
            
        except Exception as e:
            return None, f"重做失败: {e}"
    
    def get_history_list(self):
        return [
            {
                'action': r['action'],
                'file': os.path.basename(r['original_path']),
                'time': r['time_str'],
                'description': r['description']
            }
            for r in reversed(self.history)
        ]
    
    def can_undo(self):
        return len(self.history) > 0
    
    def can_redo(self):
        return len(self.redo_stack) > 0
    
    def clear_history(self):
        self.history.clear()
        self.redo_stack.clear()
        try:
            for f in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, f))
        except:
            pass
    
    def cleanup_old(self):
        try:
            files = []
            for f in os.listdir(self.temp_dir):
                path = os.path.join(self.temp_dir, f)
                files.append((path, os.path.getmtime(path)))
            
            files.sort(key=lambda x: x[1])
            
            while len(files) > self.max_history * 2:
                os.remove(files[0][0])
                files.pop(0)
        except:
            pass

_history_manager = None

def get_history_manager():
    global _history_manager
    if _history_manager is None:
        _history_manager = HistoryManager()
    return _history_manager