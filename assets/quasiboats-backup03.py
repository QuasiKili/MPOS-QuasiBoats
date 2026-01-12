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
        self.drag_start_row = None
        self.drag_start_col = None

    def get_cells(self):
        """Return list of (row, col) tuples occupied by this boat"""
        cells = []
        for i in range(self.length):
            if self.is_horizontal:
                cells.append((self.row, self.col + i))
            else:
                cells.append((self.row + i, self.col))
        return cells

    def can_move_to(self, new_row, new_col, grid_size, all_boats):
        """Check if boat can move to new position"""
        # Check bounds
        if new_row < 0 or new_col < 0:
            return False
        if self.is_horizontal:
            if new_col + self.length > grid_size or new_row >= grid_size:
                return False
        else:
            if new_row + self.length > grid_size or new_col >= grid_size:
                return False

        # Get new cells
        new_cells = []
        for i in range(self.length):
            if self.is_horizontal:
                new_cells.append((new_row, new_col + i))
            else:
                new_cells.append((new_row + i, new_col))

        # Check if new cells are occupied by other boats
        new_cells_set = set(new_cells)
        for boat in all_boats:
            if boat is self:
                continue
            occupied = set(boat.get_cells())
            if new_cells_set & occupied:
                return False

        return True


class QuasiBoats(Activity):
    """Rush Hour style puzzle game with boats in a harbor"""

    # Asset path
    ASSET_PATH = "M:apps/com.quasikili.quasiboats/assets/"

    # Screen dimensions
    SCREEN_WIDTH = 320
    SCREEN_HEIGHT = 240

    # Game constants
    # CELL_SIZE = 32  # Smaller cells to fit better
    CELL_SIZE = 20  # Smaller cells to fit better
    MIN_GRID_SIZE = 5
    MAX_GRID_SIZE = 8  # Reduced max for better fit
    DEFAULT_GRID_SIZE = 6

    # UI dimensions
    TOP_BAR_HEIGHT = 35
    BOTTOM_BAR_HEIGHT = 30

    # Grid position
    grid_offset_x = 0
    grid_offset_y = 0

    # Game state
    grid_size = DEFAULT_GRID_SIZE
    boats = []
    player_boat = None
    selected_boat = None
    dragging_boat = None
    move_count = 0
    start_time = 0
    game_won = False
    current_seed = 0

    # Animation
    last_time = 0

    # UI Elements
    screen = None
    water_bg = None
    grid_container = None
    exit_row = 0

    # UI labels
    moves_label = None
    time_label = None
    seed_label = None
    win_label = None
    size_btn_label = None

    def onCreate(self):
        print("Quasi Boats starting...")

        # Load preferences
        prefs = mpos.config.SharedPreferences("com.quasikili.quasiboats")
        self.grid_size = prefs.get_int("grid_size", self.DEFAULT_GRID_SIZE)

        # Create screen
        self.screen = lv.obj()
        self.screen.set_style_pad_all(0, 0)
        self.screen.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.screen.remove_flag(lv.obj.FLAG.SCROLLABLE)

        # Make screen focusable
        focusgroup = lv.group_get_default()
        if focusgroup:
            focusgroup.add_obj(self.screen)

        # Event handlers
        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)

        # Create UI
        self.create_ui()

        # Start new game
        self.new_game()

        self.setContentView(self.screen)
        print("Quasi Boats created")

    def create_ui(self):
        """Create the UI elements"""

        # Create fullscreen water background
        self.water_bg = lv.obj(self.screen)
        self.water_bg.set_size(lv.pct(100), lv.pct(100))
        self.water_bg.set_pos(0, 0)
        self.water_bg.set_style_bg_color(lv.color_hex(0x4A90E2), 0)  # Water blue
        self.water_bg.set_style_border_width(0, 0)
        self.water_bg.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.water_bg.remove_flag(lv.obj.FLAG.SCROLLABLE)

        # Create top info bar (semi-transparent)
        top_bar = lv.obj(self.screen)
        top_bar.set_size(lv.pct(100), self.TOP_BAR_HEIGHT)
        top_bar.set_pos(0, 0)
        top_bar.set_style_bg_color(lv.color_hex(0x34495E), 0)
        top_bar.set_style_bg_opa(200, 0)
        top_bar.set_style_border_width(0, 0)
        top_bar.set_style_pad_all(5, 0)
        top_bar.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)

        # Moves counter
        self.moves_label = lv.label(top_bar)
        self.moves_label.set_text("Moves: 0")
        self.moves_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        self.moves_label.set_style_text_font(lv.font_montserrat_14, 0)
        self.moves_label.align(lv.ALIGN.LEFT_MID, 5, 0)

        # Timer
        self.time_label = lv.label(top_bar)
        self.time_label.set_text("0:00")
        self.time_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        self.time_label.set_style_text_font(lv.font_montserrat_14, 0)
        self.time_label.align(lv.ALIGN.CENTER, 0, 0)

        # Seed display
        self.seed_label = lv.label(top_bar)
        self.seed_label.set_text("0")
        self.seed_label.set_style_text_color(lv.color_hex(0xF39C12), 0)
        self.seed_label.set_style_text_font(lv.font_montserrat_14, 0)
        self.seed_label.align(lv.ALIGN.RIGHT_MID, -5, 0)

        # Calculate grid position (centered vertically between top and bottom bars)
        available_height = self.SCREEN_HEIGHT - self.TOP_BAR_HEIGHT - self.BOTTOM_BAR_HEIGHT
        grid_pixel_size = self.grid_size * self.CELL_SIZE

        self.grid_offset_x = (self.SCREEN_WIDTH - grid_pixel_size) // 2
        self.grid_offset_y = self.TOP_BAR_HEIGHT + (available_height - grid_pixel_size) // 2

        # Create container for grid
        self.grid_container = lv.obj(self.screen)
        self.grid_container.set_size(grid_pixel_size, grid_pixel_size)
        self.grid_container.set_pos(self.grid_offset_x, self.grid_offset_y)
        self.grid_container.set_style_bg_opa(0, 0)  # Transparent
        self.grid_container.set_style_border_width(2, 0)
        self.grid_container.set_style_border_color(lv.color_hex(0x2C3E50), 0)
        self.grid_container.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.grid_container.remove_flag(lv.obj.FLAG.SCROLLABLE)

        # Create exit indicator (wooden dock on right side, middle row)
        self.exit_row = self.grid_size // 2
        exit_marker = lv.obj(self.grid_container)
        exit_marker.set_size(self.CELL_SIZE, self.CELL_SIZE)
        exit_marker.set_pos((self.grid_size - 1) * self.CELL_SIZE, self.exit_row * self.CELL_SIZE)
        exit_marker.set_style_bg_color(lv.color_hex(0x8B4513), 0)  # Brown dock
        exit_marker.set_style_border_color(lv.color_hex(0x654321), 0)
        exit_marker.set_style_border_width(2, 0)
        exit_marker.set_style_radius(0, 0)

        # Arrow on exit
        arrow_label = lv.label(exit_marker)
        arrow_label.set_text(lv.SYMBOL.RIGHT)
        arrow_label.set_style_text_color(lv.color_hex(0xFFD700), 0)
        arrow_label.center()

        # Bottom button bar
        button_bar = lv.obj(self.screen)
        button_bar.set_size(lv.pct(100), self.BOTTOM_BAR_HEIGHT)
        button_bar.set_pos(0, self.SCREEN_HEIGHT - self.BOTTOM_BAR_HEIGHT)
        button_bar.set_style_bg_color(lv.color_hex(0x34495E), 0)
        button_bar.set_style_bg_opa(200, 0)
        button_bar.set_style_border_width(0, 0)
        button_bar.set_style_pad_all(3, 0)
        button_bar.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)

        # Reset button
        reset_btn = lv.button(button_bar)
        reset_btn.set_size(70, 24)
        reset_btn.align(lv.ALIGN.LEFT_MID, 5, 0)
        reset_btn.add_event_cb(self.on_reset, lv.EVENT.CLICKED, None)
        reset_label = lv.label(reset_btn)
        reset_label.set_text("Reset")
        reset_label.set_style_text_font(lv.font_montserrat_12, 0)
        reset_label.center()

        # New game button
        new_btn = lv.button(button_bar)
        new_btn.set_size(70, 24)
        new_btn.align(lv.ALIGN.CENTER, -40, 0)
        new_btn.add_event_cb(self.on_new_game, lv.EVENT.CLICKED, None)
        new_label = lv.label(new_btn)
        new_label.set_text("New")
        new_label.set_style_text_font(lv.font_montserrat_12, 0)
        new_label.center()

        # Grid size button
        size_btn = lv.button(button_bar)
        size_btn.set_size(70, 24)
        size_btn.align(lv.ALIGN.CENTER, 40, 0)
        size_btn.add_event_cb(self.on_change_size, lv.EVENT.CLICKED, None)
        self.size_btn_label = lv.label(size_btn)
        self.size_btn_label.set_text(f"{self.grid_size}x{self.grid_size}")
        self.size_btn_label.set_style_text_font(lv.font_montserrat_12, 0)
        self.size_btn_label.center()

        # Win message (hidden initially)
        self.win_label = lv.label(self.screen)
        self.win_label.set_text("You Win!")
        self.win_label.set_style_text_font(lv.font_montserrat_28_compressed, 0)
        self.win_label.set_style_text_color(lv.color_hex(0x2ECC71), 0)
        self.win_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.win_label.align(lv.ALIGN.CENTER, 0, 0)
        self.win_label.add_flag(lv.obj.FLAG.HIDDEN)

    def new_game(self, seed=None):
        """Generate a new random puzzle"""
        if seed is None:
            seed = random.randint(1, 999999)

        self.current_seed = seed
        self.seed_label.set_text(f"#{seed}")

        random.seed(seed)

        # Clear existing boats
        for boat in self.boats:
            if boat.img:
                boat.img.delete()
        self.boats = []
        self.selected_boat = None
        self.dragging_boat = None

        # Reset counters
        self.move_count = 0
        self.start_time = time.ticks_ms()
        self.game_won = False
        self.moves_label.set_text("Moves: 0")
        self.win_label.add_flag(lv.obj.FLAG.HIDDEN)

        # Generate puzzle
        self.exit_row = self.grid_size // 2

        # Create player boat (always horizontal, on exit row, length 2)
        player_col = random.randint(0, self.grid_size - 4)
        self.player_boat = Boat(self.exit_row, player_col, 2, True, True, 'red')
        self.boats.append(self.player_boat)

        # Generate obstacle yachts
        num_obstacles = min(self.grid_size + 2, 12)
        colors = ['white', 'blue', 'yellow', 'green', 'pink']

        attempts = 0
        while len(self.boats) < num_obstacles and attempts < 100:
            attempts += 1

            length = random.choice([2, 3, 3, 4])
            is_horizontal = random.choice([True, False])
            color = random.choice(colors)

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

            new_boat = Boat(row, col, length, is_horizontal, False, color)

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

        print(f"New game: seed {seed}, {len(self.boats)} boats")

    def create_boat_images(self):
        """Create LVGL images for all boats"""
        for boat in self.boats:
            if boat.is_player:
                orientation = 'h' if boat.is_horizontal else 'v'
                src = f"{self.ASSET_PATH}player_{orientation}{boat.length}.png"
            else:
                orientation = 'h' if boat.is_horizontal else 'v'
                src = f"{self.ASSET_PATH}yacht_{boat.color}_{orientation}{boat.length}.png"

            img = lv.image(self.grid_container)
            img.set_src(src)

            x = boat.col * self.CELL_SIZE
            y = boat.row * self.CELL_SIZE
            img.set_pos(x, y)

            # Make draggable
            img.add_flag(lv.obj.FLAG.CLICKABLE)
            img.add_event_cb(lambda e, b=boat: self.on_boat_pressed(e, b),
                           lv.EVENT.PRESSED, None)
            img.add_event_cb(lambda e, b=boat: self.on_boat_pressing(e, b),
                           lv.EVENT.PRESSING, None)
            img.add_event_cb(lambda e, b=boat: self.on_boat_released(e, b),
                           lv.EVENT.RELEASED, None)

            boat.img = img

    def on_boat_pressed(self, event, boat):
        """Handle boat press start"""
        if self.game_won:
            return

        self.selected_boat = boat
        self.dragging_boat = boat
        boat.drag_start_row = boat.row
        boat.drag_start_col = boat.col

        # Visual feedback
        boat.img.set_style_outline_width(2, 0)
        boat.img.set_style_outline_color(lv.color_hex(0xF39C12), 0)

    def on_boat_pressing(self, event, boat):
        """Handle boat dragging"""
        if not self.dragging_boat or self.game_won:
            return

        # Get touch position relative to grid
        indev = lv.indev_active()
        point = lv.point_t()
        indev.get_point(point)

        # Convert to grid coordinates
        grid_x = point.x - self.grid_offset_x
        grid_y = point.y - self.grid_offset_y

        new_col = grid_x // self.CELL_SIZE
        new_row = grid_y // self.CELL_SIZE

        # Constrain movement to boat's orientation
        if boat.is_horizontal:
            new_row = boat.row  # Lock row
        else:
            new_col = boat.col  # Lock column

        # Check if valid move
        if boat.can_move_to(new_row, new_col, self.grid_size, self.boats):
            # Update visual position
            x = new_col * self.CELL_SIZE
            y = new_row * self.CELL_SIZE
            boat.img.set_pos(x, y)

    def on_boat_released(self, event, boat):
        """Handle boat release - snap to grid"""
        if not self.dragging_boat or self.game_won:
            return

        # Get current position
        x = boat.img.get_x()
        y = boat.img.get_y()

        # Snap to grid
        new_col = round(x / self.CELL_SIZE)
        new_row = round(y / self.CELL_SIZE)

        # Constrain to boat orientation
        if boat.is_horizontal:
            new_row = boat.row
        else:
            new_col = boat.col

        # Check if valid final position
        if boat.can_move_to(new_row, new_col, self.grid_size, self.boats):
            # Check if boat actually moved
            if new_row != boat.drag_start_row or new_col != boat.drag_start_col:
                boat.row = new_row
                boat.col = new_col
                self.move_count += 1
                self.moves_label.set_text(f"Moves: {self.move_count}")

                # Check win condition
                if (boat.is_player and
                    boat.row == self.exit_row and
                    boat.col + boat.length >= self.grid_size):
                    self.on_win()
        else:
            # Invalid position - snap back to start
            new_row = boat.drag_start_row
            new_col = boat.drag_start_col
            boat.row = new_row
            boat.col = new_col

        # Snap to grid visually
        x = new_col * self.CELL_SIZE
        y = new_row * self.CELL_SIZE
        boat.img.set_pos(x, y)

        # Remove visual feedback
        boat.img.set_style_outline_width(0, 0)

        self.dragging_boat = None

    def move_selected_boat(self, direction):
        """Move selected boat with keyboard"""
        if not self.selected_boat or self.game_won:
            return

        boat = self.selected_boat
        new_row = boat.row
        new_col = boat.col

        if direction == 'up' and not boat.is_horizontal:
            new_row -= 1
        elif direction == 'down' and not boat.is_horizontal:
            new_row += 1
        elif direction == 'left' and boat.is_horizontal:
            new_col -= 1
        elif direction == 'right' and boat.is_horizontal:
            new_col += 1
        else:
            return

        if boat.can_move_to(new_row, new_col, self.grid_size, self.boats):
            boat.row = new_row
            boat.col = new_col

            x = new_col * self.CELL_SIZE
            y = new_row * self.CELL_SIZE
            boat.img.set_pos(x, y)

            self.move_count += 1
            self.moves_label.set_text(f"Moves: {self.move_count}")

            if (boat.is_player and
                boat.row == self.exit_row and
                boat.col + boat.length >= self.grid_size):
                self.on_win()

    def on_win(self):
        """Handle winning the puzzle"""
        self.game_won = True
        elapsed = time.ticks_diff(time.ticks_ms(), self.start_time) // 1000

        minutes = elapsed // 60
        seconds = elapsed % 60

        self.win_label.set_text(f"You Win!\n{self.move_count} moves\n{minutes}:{seconds:02d}")
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
        # Delete old containers
        if self.grid_container:
            self.grid_container.delete()
        if self.win_label:
            self.win_label.delete()

        # Clear boat list
        self.boats = []

        # Recreate UI elements that depend on grid size
        available_height = self.SCREEN_HEIGHT - self.TOP_BAR_HEIGHT - self.BOTTOM_BAR_HEIGHT
        grid_pixel_size = self.grid_size * self.CELL_SIZE

        self.grid_offset_x = (self.SCREEN_WIDTH - grid_pixel_size) // 2
        self.grid_offset_y = self.TOP_BAR_HEIGHT + (available_height - grid_pixel_size) // 2

        # Recreate grid container
        self.grid_container = lv.obj(self.screen)
        self.grid_container.set_size(grid_pixel_size, grid_pixel_size)
        self.grid_container.set_pos(self.grid_offset_x, self.grid_offset_y)
        self.grid_container.set_style_bg_opa(0, 0)
        self.grid_container.set_style_border_width(2, 0)
        self.grid_container.set_style_border_color(lv.color_hex(0x2C3E50), 0)
        self.grid_container.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.grid_container.remove_flag(lv.obj.FLAG.SCROLLABLE)

        # Recreate exit marker
        self.exit_row = self.grid_size // 2
        exit_marker = lv.obj(self.grid_container)
        exit_marker.set_size(self.CELL_SIZE, self.CELL_SIZE)
        exit_marker.set_pos((self.grid_size - 1) * self.CELL_SIZE, self.exit_row * self.CELL_SIZE)
        exit_marker.set_style_bg_color(lv.color_hex(0x8B4513), 0)
        exit_marker.set_style_border_color(lv.color_hex(0x654321), 0)
        exit_marker.set_style_border_width(2, 0)
        exit_marker.set_style_radius(0, 0)

        arrow_label = lv.label(exit_marker)
        arrow_label.set_text(lv.SYMBOL.RIGHT)
        arrow_label.set_style_text_color(lv.color_hex(0xFFD700), 0)
        arrow_label.center()

        # Recreate win label
        self.win_label = lv.label(self.screen)
        self.win_label.set_style_text_font(lv.font_montserrat_28_compressed, 0)
        self.win_label.set_style_text_color(lv.color_hex(0x2ECC71), 0)
        self.win_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.win_label.align(lv.ALIGN.CENTER, 0, 0)
        self.win_label.add_flag(lv.obj.FLAG.HIDDEN)

        # Start new game
        self.new_game()

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

    def update_frame(self, a, b):
        """Main game loop - update timer"""
        if not self.game_won:
            elapsed = time.ticks_diff(time.ticks_ms(), self.start_time) // 1000
            minutes = elapsed // 60
            seconds = elapsed % 60
            self.time_label.set_text(f"{minutes}:{seconds:02d}")

    def onResume(self, screen):
        """Activity goes foreground"""
        mpos.ui.task_handler.add_event_cb(self.update_frame, 1)

    def onPause(self, screen):
        """Activity goes background"""
        mpos.ui.task_handler.remove_event_cb(self.update_frame)