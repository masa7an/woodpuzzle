"""
ステージファイル管理モジュール
.stageファイルの読み込みと保存を担当
"""

import os


class StageLoader:
    """ステージファイルの読み込み・保存を管理"""
    
    @staticmethod
    def save_stage(filepath, stage_id, name, difficulty, grid_shape, pieces):
        """
        ステージを.stageファイルに保存
        
        Args:
            filepath: 保存先パス
            stage_id: ステージID（例: STAGE_001）
            name: ステージ名
            difficulty: 難易度（1-5）
            grid_shape: グリッド形状（2D配列）
            pieces: ピース情報のリスト [{id, position, cells}, ...]
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            # ヘッダー
            f.write("# STAGE DEFINITION\n")
            f.write(f"stage_id: {stage_id}\n")
            f.write(f"name: {name}\n")
            f.write(f"difficulty: {difficulty}\n")
            f.write("\n")
            
            # グリッド形状
            f.write("# GRID SHAPE (1=valid, 0=invalid)\n")
            f.write("grid:\n")
            for row in grid_shape:
                f.write(" ".join(str(cell) for cell in row) + "\n")
            f.write("\n")
            
            # ピース定義
            f.write("# PIECES\n")
            for piece in pieces:
                f.write(f"piece {piece['id']}:\n")
                f.write(f"  position: {piece['position'][0]},{piece['position'][1]}\n")
                cells_str = " ".join(f"({r},{c})" for r, c in piece['cells'])
                f.write(f"  cells: {cells_str}\n")
                f.write("\n")
    
    @staticmethod
    def load_stage(filepath):
        """
        .stageファイルからステージを読み込み
        
        Returns:
            dict: {
                'stage_id': str,
                'name': str,
                'difficulty': int,
                'grid_shape': [[int]],
                'pieces': [{id, position, cells}, ...]
            }
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        result = {
            'stage_id': '',
            'name': '',
            'difficulty': 1,
            'grid_shape': [],
            'pieces': []
        }
        
        current_section = None
        current_piece = None
        
        for line in lines:
            line = line.strip()
            
            # コメントと空行をスキップ
            if not line or line.startswith('#'):
                continue
            
            # ヘッダー情報
            if line.startswith('stage_id:'):
                result['stage_id'] = line.split(':', 1)[1].strip()
            elif line.startswith('name:'):
                result['name'] = line.split(':', 1)[1].strip()
            elif line.startswith('difficulty:'):
                result['difficulty'] = int(line.split(':', 1)[1].strip())
            elif line == 'grid:':
                current_section = 'grid'
            elif line.startswith('piece '):
                current_section = 'piece'
                piece_id = line.split()[1].rstrip(':')
                current_piece = {'id': piece_id, 'position': (0, 0), 'cells': []}
                result['pieces'].append(current_piece)
            elif current_section == 'grid':
                # グリッド行をパース
                row = [int(x) for x in line.split()]
                result['grid_shape'].append(row)
            elif current_section == 'piece' and current_piece:
                if line.startswith('position:'):
                    pos_str = line.split(':', 1)[1].strip()
                    row, col = map(int, pos_str.split(','))
                    current_piece['position'] = (row, col)
                elif line.startswith('cells:'):
                    cells_str = line.split(':', 1)[1].strip()
                    # (row,col) 形式をパース
                    cells = []
                    for cell in cells_str.split():
                        cell = cell.strip('()')
                        r, c = map(int, cell.split(','))
                        cells.append((r, c))
                    current_piece['cells'] = cells
        
        return result
    
    @staticmethod
    def list_stages(stages_dir):
        """
        stagesディレクトリ内の.stageファイル一覧を取得
        
        Returns:
            list: ファイルパスのリスト
        """
        if not os.path.exists(stages_dir):
            return []
        
        files = []
        for f in os.listdir(stages_dir):
            if f.endswith('.stage'):
                files.append(os.path.join(stages_dir, f))
        return sorted(files)
