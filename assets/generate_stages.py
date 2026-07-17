import os
import random
import json

STAGES_DIR = 'stages'
os.makedirs(STAGES_DIR, exist_ok=True)

# 11x11 grid default
GRID_SIZE = 11

def create_empty_grid():
    return [[0] * GRID_SIZE for _ in range(GRID_SIZE)]

# --- Grid Shapes ---
def get_shape(stage_name):
    grid = create_empty_grid()
    
    # helper
    def fill_rect(r1, c1, r2, c2):
        for r in range(r1, r2+1):
            for c in range(c1, c2+1):
                if 0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE:
                    grid[r][c] = 1
    def set_cell(r, c):
        if 0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE:
            grid[r][c] = 1

    if stage_name == 'Apple':
        # Apply shape
        fill_rect(2, 2, 8, 8) # Body
        grid[1][5] = 1 # Stem
        grid[2][2] = 0; grid[2][8] = 0; grid[8][2] = 0; grid[8][8] = 0 # Round corners
        grid[8][5] = 0 # Bottom dimple
        grid[2][5] = 0 # Top dimple
        
    elif stage_name == 'Mushroom':
        fill_rect(2, 2, 5, 8) # Cap
        grid[2][2]=0; grid[2][8]=0 # Round cap top
        fill_rect(6, 4, 9, 6) # Stem
        
    elif stage_name == 'Umbrella':
        fill_rect(2, 1, 5, 9) # Top
        grid[2][1]=0; grid[2][9]=0
        grid[5][1]=0; grid[5][9]=0 # Curve bottom corners a bit?
        fill_rect(6, 5, 8, 5) # Handle
        grid[9][5]=1; grid[9][6]=1 # Handle curve
        
    elif stage_name == 'Star':
        # Center
        fill_rect(4, 4, 6, 6)
        # Points
        grid[2][5]=1; grid[3][5]=1 # Top
        grid[8][5]=1; grid[7][5]=1 # Bottom
        grid[5][2]=1; grid[5][3]=1 # Left
        grid[5][8]=1; grid[5][7]=1 # Right
        # Diagonals
        grid[3][3]=1; grid[3][7]=1
        grid[7][3]=1; grid[7][7]=1

    elif stage_name == 'Dog':
        fill_rect(4, 2, 6, 7) # Body
        fill_rect(2, 6, 4, 8) # Head
        grid[2][6]=0 # Ear shape
        grid[7][2]=1; grid[7][3]=1 # Back Leg
        grid[7][6]=1; grid[7][7]=1 # Front Leg
        grid[4][1]=1 # Tail

    elif stage_name == 'Cat':
        fill_rect(4, 3, 8, 7) # Body
        fill_rect(2, 4, 4, 6) # Head
        grid[1][4]=1; grid[1][6]=1 # Ears
        grid[7][8]=1; grid[6][9]=1; grid[5][9]=1 # Tail

    elif stage_name == 'Flower':
        # Center
        fill_rect(4, 4, 6, 6)
        # Petals
        fill_rect(2, 4, 3, 6) # Top
        fill_rect(7, 4, 8, 6) # Bottom
        fill_rect(4, 2, 6, 3) # Left
        fill_rect(4, 7, 6, 8) # Right

    elif stage_name == 'Car':
        fill_rect(5, 1, 7, 9) # Body lower
        fill_rect(3, 3, 5, 7) # Cabin
        grid[8][2]=1; grid[8][3]=1 # Wheel 1
        grid[8][7]=1; grid[8][8]=1 # Wheel 2
        
    elif stage_name == 'Robot':
        fill_rect(2, 4, 3, 6) # Head
        fill_rect(4, 3, 7, 7) # Body
        fill_rect(4, 1, 6, 2) # Arm L
        fill_rect(4, 8, 6, 9) # Arm R
        fill_rect(8, 3, 9, 4) # Leg L
        fill_rect(8, 6, 9, 7) # Leg R

    elif stage_name == 'Crown':
        fill_rect(5, 2, 8, 8) # Base
        grid[4][2]=1; grid[3][2]=1 # Point L
        grid[4][8]=1; grid[3][8]=1 # Point R
        grid[4][5]=1; grid[3][5]=1 # Point C
        grid[4][3]=0; grid[4][7]=0 # Gaps
        
    return grid

# --- Piece Generation ---

def generate_pieces(grid, min_size=4, max_size=6):
    rows = len(grid)
    cols = len(grid[0])
    used = [[False]*cols for _ in range(rows)]
    
    target_cells = []
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 1:
                target_cells.append((r, c))
    
    pieces = []
    
    attempts = 0
    while len(target_cells) > 0 and attempts < 1000:
        # Find start cell
        start_cell = None
        for r, c in target_cells:
            if not used[r][c]:
                start_cell = (r, c)
                break
        
        if not start_cell:
            break
            
        # Try to grow a piece
        current_piece = [start_cell]
        used[start_cell[0]][start_cell[1]] = True
        
        target_size = random.randint(min_size, max_size)
        
        # Simple BFS/Random growth
        candidates = []
        
        def add_candidates(r, c):
            for dr, dc in [(0,1), (0,-1), (1,0), (-1,0)]:
                nr, nc = r+dr, c+dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if grid[nr][nc] == 1 and not used[nr][nc]:
                        if (nr, nc) not in candidates and (nr, nc) not in current_piece:
                            candidates.append((nr, nc))
                            
        add_candidates(*start_cell)
        
        while len(current_piece) < target_size and candidates:
            # Pick a random candidate that is adjacent to current piece
            # To simulate "chunkiness", prefer neighbors of recently added cells?
            # Random is fine for now
            idx = random.randrange(len(candidates))
            next_cell = candidates.pop(idx)
            
            if used[next_cell[0]][next_cell[1]]:
                continue
                
            current_piece.append(next_cell)
            used[next_cell[0]][next_cell[1]] = True
            add_candidates(*next_cell)
            
        pieces.append(current_piece)
        
        # Remove used from target_cells logic (not strictly needed since we check used matrix)
        new_targets = []
        for r, c in target_cells:
            if not used[r][c]:
                new_targets.append((r, c))
        target_cells = new_targets
        
        attempts += 1

    # Check validity (no single small pieces if possible?)
    # For now, just return what we have. If 1-2 cell pieces remain, it's fine for auto-gen basic.
    return pieces

def save_stage(stage_id, name, difficulty, grid, pieces):
    filename = f"STAGE_{int(stage_id):03d}.stage"
    filepath = os.path.join(STAGES_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"stage_id: STAGE_{int(stage_id):03d}\n")
        f.write(f"name: {name}\n")
        f.write(f"difficulty: {difficulty}\n")
        f.write("grid:\n")
        for row in grid:
            f.write(" ".join(map(str, row)) + "\n")
        
        for i, cells in enumerate(pieces):
            # Create a localized piece
            # Find top-left
            min_r = min(r for r, c in cells)
            min_c = min(c for r, c in cells)
            
            # ID: I, J, K...
            piece_id = chr(ord('A') + i)
            # If > Z, use AA, AB? For now assume < 26 pieces.
            # Fix piece_id generation later if needed, but game logic supports generic strings
            if i >= 26:
                piece_id = f"P{i}"
            
            local_cells = [(r - min_r, c - min_c) for r, c in cells]
            
            # Format: 'position: r,c' maps to the top-left of the piece in the grid
            # wait, game logic expects 'position' to be the correct placement?
            # Yes, solution uses absolute position.
            # But the piece object uses relative cells.
            # So: position = (min_r, min_c), cells = local_cells
            
            f.write(f"piece {piece_id}:\n")
            f.write(f"  position: {min_r},{min_c}\n")
            cells_str = " ".join([f"({r},{c})" for r, c in local_cells])
            f.write(f"  cells: {cells_str}\n")
    
    print(f"Generated {filename}")

# --- Main ---
STAGES = [
    (11, 'Apple', 1),
    (12, 'Mushroom', 2),
    (13, 'Umbrella', 2),
    (14, 'Star', 3),
    (15, 'Dog', 3),
    (16, 'Cat', 3),
    (17, 'Flower', 4),
    (18, 'Car', 4),
    (19, 'Robot', 5),
    (20, 'Crown', 5),
]

for stage_num, name, diff in STAGES:
    grid = get_shape(name)
    
    # Adjust piece size based on difficulty/stage
    # Lower stage (11) -> Larger pieces (easier)
    # Higher stage (20) -> Smaller pieces (harder)
    
    if stage_num <= 13:
        min_p = 5
        max_p = 8  # Big chunks
    elif stage_num <= 16:
        min_p = 4
        max_p = 6
    else:
        min_p = 3
        max_p = 5  # Standard
        
    # Retry loop to ensure good generation
    best_pieces = []
    min_piece_count = 999
    
    for _ in range(20): # Try 20 times to find best fit
        pieces = generate_pieces(grid, min_p, max_p)
        # Check if any tiny pieces left (size 1 or 2) - undesireable
        tiny_pieces = sum(1 for p in pieces if len(p) <= 2)
        
        if tiny_pieces == 0:
            best_pieces = pieces
            break
        
        if len(pieces) < min_piece_count:
            min_piece_count = len(pieces)
            best_pieces = pieces
            
    save_stage(stage_num, name, diff, grid, best_pieces)
