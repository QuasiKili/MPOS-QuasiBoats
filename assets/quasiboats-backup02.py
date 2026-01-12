import time
import random

from mpos.apps import Activity
import mpos.ui
import mpos.config
from mpos.ui.focus_direction import emulate_focus_obj

try:
    import lvgl as lv  # pyright: ignore[reportMissingModuleSource]
except ImportError:
    pass  # lv is already available as a global in MicroPython OS


class Boat:
    """Represents a boat on the grid (player or yacht obstacle)"""
    
    def __init__(self, row, col, length, is_horizontal, is_player=False, color='white'):
        self.row = row  # Top-left position
        self.col = col
        self.length = length  # 2, 3, or 4 cells
        self.is_horizontal = is_horizontal
        self.is_player = is_player
        self.color = color  # For yachts: white, blue, yellow, green, pink
        self.img = None  # LVGL image object
    
    def get_cells(self):
        """Return list of (row, col) tuples occupied by this boat"""
        cells = []
        for i in range(self.length):
            if self.is_horizontal:
                cells.append((self.row, self.col + i))
            else:
                cells.append((self.row + i, self.col))
        return cells
    
    def can_move(self, direction, grid_size, all_boats):
        """Check if boat can move in direction (returns new position or None)"""
        if direction == 'up' and not self.is_horizontal:
            new_row = self.row - 1
            if new_row < 0:
                return None
            new_cells = [(new_row + i, self.col) for i in range(self.length)]
        elif direction == 'down' and not self.is_horizontal:
            new_row = self.row + 1
            if new_row + self.length > grid_size:
                return None
            new_cells = [(new_row + i, self.col) for i in range(self.length)]
        elif direction == 'left' and self.is_horizontal:
            new_col = self.col - 1
            if new_col < 0:
                return None
            new_cells = [(self.row, new_col + i) for i in range(self.length)]
        elif direction == 'right' and self.is_horizontal:
            new_col = self.col + 1
            if new_col + self.length > grid_size:
                return None
            new_cells = [(self.row, new_col + i) for i in range(self.length)]
        else:
            return None  # Invalid direction for boat orientation
        
        # Check if new cells are occupied by other boats
        current_cells = set(self.get_cells())
        for boat in all_boats:
            if boat is self:
                continue
            occupied = set(boat.get_cells())
            # Check if any new cell (that we're not currently in) is occupied
            for cell in new_cells:
                if cell in occupied and cell not in current_cells:
                    return None
        
        return (new_row if direction in ['up', 'down'] else self.row,
                new_col if direction in ['left', 'right'] else self.col)


class QuasiBoats(Activity):
    """Rush Hour style puzzle game with boats in a harbor"""
    
    # Asset path
    ASSET_PATH = "M:apps/com.quasikili.quasiboats/assets/"
    
    # Screen dimensions
    SCREEN_WIDTH = 320
    SCREEN_HEIGHT = 240
    
    # Game constants
    CELL_SIZE = 40
    MIN_GRID_SIZE = 5
    MAX_GRID_SIZE = 12
    DEFAULT_GRID_SIZE = 6
    
    # Grid position (centered)
    grid_offset_x = 0
    grid_offset_y = 0
    
    # Game state
    grid_size = DEFAULT_GRID_SIZE
    boats = []  # List of Boat objects
    player_boat = None
    selected_boat = None
    move_count = 0
    start_time = 0
    game_won = False
    current_seed = 0
    
    # Animation
    wave_frame = 0
    wave_timer = 0
    last_time = 0
    
    # UI Elements
    screen = None
    grid_container = None
    water_tiles = []  # 2D array of water tile images
    boat_images = []
    exit_row = 0  # Which row has the exit (usually middle)
    
    # UI labels
    moves_label = None
    time_label = None
    seed_label = None
    win_label = None
    
    def onCreate(self):
        print("Quasi Boats starting...")
        
        # Load preferences
        prefs = mpos.config.SharedPreferences("com.quasikili.quasiboats")
        self.grid_size = prefs.get_int("grid_size", self.DEFAULT_GRID_SIZE)
        
        # Create screen
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_hex(0x2C3E50), 0)  # Dark blue-gray
        self.screen.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.screen.remove_flag(lv.obj.FLAG.SCROLLABLE)
        
        # Make screen focusable
        focusgroup = lv.group_get_default()
        if focusgroup:
            focusgroup.add_obj(self.screen)
        
        # Event handlers
        self.screen.add_event_cb(self.on_tap, lv.EVENT.CLICKED, None)
        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)
        
        # Create UI
        self.create_ui()
        
        # Start new game
        self.new_game()
        
        self.setContentView(self.screen)
        print("Quasi Boats created")
    
    def create_ui(self):
        """Create the UI elements"""
        
        # Calculate grid position (centered)
        grid_pixel_size = self.grid_size * self.CELL_SIZE
        self.grid_offset_x = (self.SCREEN_WIDTH - grid_pixel_size) // 2
        self.grid_offset_y = (self.SCREEN_HEIGHT - grid_pixel_size) // 2 + 10
        
        # Create container for grid
        self.grid_container = lv.obj(self.screen)
        self.grid_container.set_size(grid_pixel_size, grid_pixel_size)
        self.grid_container.set_pos(self.grid_offset_x, self.grid_offset_y)
        self.grid_container.set_style_bg_opa(0, 0)  # Transparent
        self.grid_container.set_style_border_width(0, 0)
        self.grid_container.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.grid_container.remove_flag(lv.obj.FLAG.SCROLLABLE)
        
        # Create water tiles
        self.water_tiles = []
        for row in range(self.grid_size):
            row_tiles = []
            for col in range(self.grid_size):
                water = lv.image(self.grid_container)
                water.set_src(f"{self.ASSET_PATH}water.png")
                water.set_pos(col * self.CELL_SIZE, row * self.CELL_SIZE)
                row_tiles.append(water)
            self.water_tiles.append(row_tiles)
        
        # Create exit indicator (on right side, middle row)
        self.exit_row = self.grid_size // 2
        exit_tile = lv.image(self.grid_container)
        exit_tile.set_src(f"{self.ASSET_PATH}exit.png")
        exit_tile.set_pos((self.grid_size - 1) * self.CELL_SIZE, 
                         self.exit_row * self.CELL_SIZE)
        
        # Create info panel at top
        info_height = 30
        info_panel = lv.obj(self.screen)
        info_panel.set_size(self.SCREEN_WIDTH, info_height)
        info_panel.set_pos(0, 0)
        info_panel.set_style_bg_color(lv.color_hex(0x34495E), 0)
        info_panel.set_style_border_width(0, 0)
        info_panel.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        
        # Moves counter
        self.moves_label = lv.label(info_panel)
        self.moves_label.set_text("Moves: 0")
        self.moves_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        self.moves_label.set_style_text_font(lv.font_montserrat_16, 0)
        self.moves_label.set_pos(10, 7)
        
        # Timer
        self.time_label = lv.label(info_panel)
        self.time_label.set_text("Time: 0:00")
        self.time_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        self.time_label.set_style_text_font(lv.font_montserrat_16, 0)
        self.time_label.set_pos(120, 7)
        
        # Seed display
        self.seed_label = lv.label(info_panel)
        self.seed_label.set_text("Seed: 0")
        self.seed_label.set_style_text_color(lv.color_hex(0xF39C12), 0)
        self.seed_label.set_style_text_font(lv.font_montserrat_14, 0)
        self.seed_label.align(lv.ALIGN.RIGHT_MID, -10, 0)
        
        # Bottom button panel
        button_panel = lv.obj(self.screen)
        button_panel.set_size(self.SCREEN_WIDTH, 30)
        button_panel.set_pos(0, self.SCREEN_HEIGHT - 30)
        button_panel.set_style_bg_color(lv.color_hex(0x34495E), 0)
        button_panel.set_style_border_width(0, 0)
        button_panel.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        
        # Reset button
        reset_btn = lv.button(button_panel)
        reset_btn.set_size(80, 24)
        reset_btn.set_pos(10, 3)
        reset_btn.add_event_cb(self.on_reset, lv.EVENT.CLICKED, None)
        reset_label = lv.label(reset_btn)
        reset_label.set_text("Reset")
        reset_label.center()
        
        # New game button
        new_btn = lv.button(button_panel)
        new_btn.set_size(80, 24)
        new_btn.set_pos(100, 3)
        new_btn.add_event_cb(self.on_new_game, lv.EVENT.CLICKED, None)
        new_label = lv.label(new_btn)
        new_label.set_text("New")
        new_label.center()
        
        # Grid size button
        size_btn = lv.button(button_panel)
        size_btn.set_size(80, 24)
        size_btn.set_pos(190, 3)
        size_btn.add_event_cb(self.on_change_size, lv.EVENT.CLICKED, None)
        self.size_btn_label = lv.label(size_btn)
        self.size_btn_label.set_text(f"{self.grid_size}x{self.grid_size}")
        self.size_btn_label.center()
        
        # Win message (hidden initially)
        self.win_label = lv.label(self.screen)
        self.win_label.set_text("You Win!")
        self.win_label.set_style_text_font(lv.font_montserrat_28_compressed, 0)
        self.win_label.set_style_text_color(lv.color_hex(0x2ECC71), 0)
        self.win_label.align(lv.ALIGN.CENTER, 0, -40)
        self.win_label.add_flag(lv.obj.FLAG.HIDDEN)
    
    def new_game(self, seed=None):
        """Generate a new random puzzle"""
        if seed is None:
            seed = random.randint(1, 999999)
        
        self.current_seed = seed
        self.seed_label.set_text(f"Seed: {seed}")
        
        random.seed(seed)
        
        # Clear existing boats
        for boat in self.boats:
            if boat.img:
                boat.img.delete()
        self.boats = []
        self.selected_boat = None
        
        # Reset counters
        self.move_count = 0
        self.start_time = time.ticks_ms()
        self.game_won = False
        self.moves_label.set_text("Moves: 0")
        self.win_label.add_flag(lv.obj.FLAG.HIDDEN)
        
        # Generate puzzle
        self.exit_row = self.grid_size // 2
        
        # Create player boat (always horizontal, on exit row, length 2)
        player_col = random.randint(0, self.grid_size - 4)  # Start away from exit
        self.player_boat = Boat(self.exit_row, player_col, 2, True, True, 'red')
        self.boats.append(self.player_boat)
        
        # Generate obstacle yachts
        num_obstacles = min(self.grid_size + 2, 15)  # More obstacles for larger grids
        colors = ['white', 'blue', 'yellow', 'green', 'pink']
        
        attempts = 0
        while len(self.boats) < num_obstacles and attempts < 100:
            attempts += 1
            
            # Random properties
            length = random.choice([2, 3, 3, 4])  # Favor length 3
            is_horizontal = random.choice([True, False])
            color = random.choice(colors)
            
            # Random position
            if is_horizontal:
                max_col = self.grid_size - length
                max_row = self.grid_size - 1
                col = random.randint(0, max_col)
                row = random.randint(0, max_row)
            else:
                max_col = self.grid_size - 1
                max_row = self.grid_size - length
                col = random.randint(0, max_col)
                row = random.randint(0, max_row)
            
            # Create boat and check if it overlaps
            new_boat = Boat(row, col, length, is_horizontal, False, color)
            
            # Check overlap
            new_cells = set(new_boat.get_cells())
            overlaps = False
            for existing in self.boats:
                if new_cells & set(existing.get_cells()):
                    overlaps = True
                    break
            
            if not overlaps:
                self.boats.append(new_boat)
        
        # Create images for boats
        self.create_boat_images()
        
        print(f"New game created with seed {seed}, {len(self.boats)} boats")
    
    def create_boat_images(self):
        """Create LVGL images for all boats"""
        for boat in self.boats:
            if boat.is_player:
                # Player rowing boat
                orientation = 'h' if boat.is_horizontal else 'v'
                src = f"{self.ASSET_PATH}player_{orientation}{boat.length}.png"
            else:
                # Yacht obstacle
                orientation = 'h' if boat.is_horizontal else 'v'
                src = f"{self.ASSET_PATH}yacht_{boat.color}_{orientation}{boat.length}.png"
            
            img = lv.image(self.grid_container)
            img.set_src(src)
            
            x = boat.col * self.CELL_SIZE
            y = boat.row * self.CELL_SIZE
            img.set_pos(x, y)
            
            # Make clickable
            img.add_flag(lv.obj.FLAG.CLICKABLE)
            img.add_event_cb(lambda e, b=boat: self.on_boat_click(e, b), 
                           lv.EVENT.CLICKED, None)
            
            boat.img = img
    
    def on_boat_click(self, event, boat):
        """Handle boat selection"""
        if self.game_won:
            return
        
        self.selected_boat = boat
        print(f"Selected {'player' if boat.is_player else 'yacht'} at ({boat.row},{boat.col})")
        
        # Visual feedback - make selected boat slightly larger
        for b in self.boats:
            if b.img:
                if b == boat:
                    b.img.set_style_outline_width(3, 0)
                    b.img.set_style_outline_color(lv.color_hex(0xF39C12), 0)
                else:
                    b.img.set_style_outline_width(0, 0)
    
    def move_selected_boat(self, direction):
        """Move the selected boat in a direction"""
        if not self.selected_boat or self.game_won:
            return
        
        result = self.selected_boat.can_move(direction, self.grid_size, self.boats)
        if result:
            new_row, new_col = result
            self.selected_boat.row = new_row
            self.selected_boat.col = new_col
            
            # Update image position
            x = new_col * self.CELL_SIZE
            y = new_row * self.CELL_SIZE
            self.selected_boat.img.set_pos(x, y)
            
            # Increment move counter
            self.move_count += 1
            self.moves_label.set_text(f"Moves: {self.move_count}")
            
            print(f"Moved to ({new_row},{new_col})")
            
            # Check win condition (player boat reaches right edge on exit row)
            if (self.selected_boat.is_player and 
                self.selected_boat.row == self.exit_row and
                self.selected_boat.col + self.selected_boat.length >= self.grid_size):
                self.on_win()
    
    def on_win(self):
        """Handle winning the puzzle"""
        self.game_won = True
        elapsed = time.ticks_diff(time.ticks_ms(), self.start_time) // 1000
        
        self.win_label.set_text(f"You Win!\n{self.move_count} moves, {elapsed}s")
        self.win_label.remove_flag(lv.obj.FLAG.HIDDEN)
        
        print(f"Puzzle solved! Moves: {self.move_count}, Time: {elapsed}s")
    
    def on_reset(self, event):
        """Reset current puzzle"""
        self.new_game(self.current_seed)
    
    def on_new_game(self, event):
        """Start new random puzzle"""
        self.new_game()
    
    def on_change_size(self, event):
        """Cycle through grid sizes"""
        self.grid_size += 1
        if self.grid_size > self.MAX_GRID_SIZE:
            self.grid_size = self.MIN_GRID_SIZE
        
        # Save preference
        editor = mpos.config.SharedPreferences("com.quasikili.quasiboats").edit()
        editor.put_int("grid_size", self.grid_size)
        editor.commit()
        
        self.size_btn_label.set_text(f"{self.grid_size}x{self.grid_size}")
        self.size_btn_label.center()
        
        # Recreate grid
        self.recreate_grid()
    
    def recreate_grid(self):
        """Recreate the grid with new size"""
        # Delete old grid
        if self.grid_container:
            self.grid_container.delete()
        
        # Delete win label
        if self.win_label:
            self.win_label.delete()
        
        # Recreate UI
        self.water_tiles = []
        self.boats = []
        self.create_ui()
        self.new_game()
    
    def on_tap(self, event):
        """Handle screen tap"""
        pass  # Boat clicks are handled by boat images
    
    def on_key(self, event):
        """Handle keyboard input"""
        key = event.get_key()
        
        if key == lv.KEY.UP:
            self.move_selected_boat('up')
        elif key == lv.KEY.DOWN:
            self.move_selected_boat('down')
        elif key == lv.KEY.LEFT:
            self.move_selected_boat('left')
        elif key == lv.KEY.RIGHT:
            self.move_selected_boat('right')
        elif key == ord('R') or key == ord('r'):
            self.on_reset(event)
        elif key == ord('N') or key == ord('n'):
            self.on_new_game(event)
        elif key == ord('S') or key == ord('s'):
            self.on_change_size(event)
        else:
            print(f"on_key: unhandled key {key}")
    
    def update_frame(self, a, b):
        """Main game loop - update timer and animations"""
        current_time = time.ticks_ms()
        
        if not self.game_won:
            # Update timer
            elapsed = time.ticks_diff(current_time, self.start_time) // 1000
            minutes = elapsed // 60
            seconds = elapsed % 60
            self.time_label.set_text(f"Time: {minutes}:{seconds:02d}")
        
        # TODO: Animate water waves (if performance allows)
        # self.wave_frame = (self.wave_frame + 1) % 4
    
    def onResume(self, screen):
        """Activity goes foreground"""
        mpos.ui.task_handler.add_event_cb(self.update_frame, 1)
    
    def onPause(self, screen):
        """Activity goes background"""
        mpos.ui.task_handler.remove_event_cb(self.update_frame)
