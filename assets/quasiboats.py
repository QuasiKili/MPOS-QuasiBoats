import time
import random

from mpos import Activity, InputManager, SharedPreferences
import mpos.ui

try:
    import lvgl as lv  # pyright: ignore[reportMissingModuleSource]
except ImportError:
    pass  # lv is already available as a global in MicroPython OS


class Boat:
    """Represents a boat on the grid (player or yacht obstacle)"""

    def __init__(self, row, col, length, is_horizontal, is_player=False, color="white"):
        self.row = row  # Top-left position
        self.col = col
        self.length = length  # 2, 3, or 4 cells
        self.is_horizontal = is_horizontal
        self.is_player = is_player
        self.color = color  # For yachts: white, blue, yellow, green, pink
        self.img = None  # LVGL image object
        self.drag_start_row = None
        self.drag_start_col = None
        self.selected = False

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
        """Check if boat can move to new position, checking for path blocking"""
        # Check bounds
        if new_row < 0 or new_col < 0:
            return False
        if self.is_horizontal:
            if new_col + self.length > grid_size or new_row >= grid_size:
                return False
        else:
            if new_row + self.length > grid_size or new_col >= grid_size:
                return False

        # Check path
        if self.is_horizontal:
            step = 1 if new_col > self.col else -1
            curr_col = self.col
            while curr_col != new_col:
                curr_col += step
                if not self._is_pos_free(self.row, curr_col, all_boats):
                    return False
        else:
            step = 1 if new_row > self.row else -1
            curr_row = self.row
            while curr_row != new_row:
                curr_row += step
                if not self._is_pos_free(curr_row, self.col, all_boats):
                    return False

        return True

    def _is_pos_free(self, row, col, all_boats):
        """Check if boat can be at this position (row, col) without overlap"""
        new_cells_set = set()
        for i in range(self.length):
            if self.is_horizontal:
                new_cells_set.add((row, col + i))
            else:
                new_cells_set.add((row + i, col))
        
        for boat in all_boats:
            if boat is self:
                continue
            for cell in boat.get_cells():
                if cell in new_cells_set:
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
    MIN_GRID_SIZE = 4
    MAX_GRID_SIZE = 10
    DEFAULT_GRID_SIZE = 6

    # Fixed grid pixel size (fullscreen height minus padding)
    GRID_PIXEL_SIZE = 230  # Leave small margin

    # UI dimensions
    RIGHT_PANEL_WIDTH = 75

    # Calculated per grid size
    cell_size = 0
    grid_offset_x = 10
    grid_offset_y = 5

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
    move_locked = False  # For keyboard control with Enter held
    drag_dots = [] # Store dot objects for selected boat
    update_timer = None # Reference to LVGL timer for frame updates

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
    menu_modal = None

    # colors
    wood_bg_color = 0x8B4513
    wood_border_color = 0x654321

    def onCreate(self):
        print("Quasi Boats starting...")

        # Get dynamic screen resolution
        d = lv.display_get_default()
        self.SCREEN_WIDTH = d.get_horizontal_resolution()
        self.SCREEN_HEIGHT = d.get_vertical_resolution()
        self.GRID_PIXEL_SIZE = self.SCREEN_HEIGHT - 10

        # Load preferences
        prefs = SharedPreferences("com.quasikili.quasiboats")
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

    def calculate_cell_size(self):
        """Calculate cell size based on grid size to fit in fixed grid area"""
        self.cell_size = self.GRID_PIXEL_SIZE // self.grid_size

    def create_ui(self):
        """Create the UI elements"""

        self.calculate_cell_size()

        # Create fullscreen water background
        self.water_bg = lv.obj(self.screen)
        self.water_bg.set_size(lv.pct(100), lv.pct(100))
        self.water_bg.set_pos(0, 0)
        self.water_bg.set_style_bg_color(lv.color_hex(0x2A84E3), 0)  # Water blue
        self.water_bg.set_style_border_width(0, 0)
        self.water_bg.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.water_bg.remove_flag(lv.obj.FLAG.SCROLLABLE)

        # Create grid container (fixed size, aligned left)
        # Added 4px for border to avoid clipping
        grid_pixel_size = self.grid_size * self.cell_size + 4

        self._create_grid_container(grid_pixel_size)

        self._create_exit_marker()


        # Right panel - Info and controls
        right_panel_content_size = self.grid_size * self.cell_size
        right_panel_x = self.grid_offset_x + right_panel_content_size + 5

        self._create_info_panel_container(right_panel_x)

        self._create_info_panel_labels(self.info_panel_container)
        self._create_win_label(self.grid_container)

        # Seed display
        self.seed_label = lv.label(self.screen)
        self.seed_label.set_text("#0")
        self.seed_label.set_style_text_color(lv.color_hex(0xF39C12), 0)
        # self.seed_label.set_pos(right_panel_x, 110) # Adjusted position
        self.seed_label.set_pos(right_panel_x, 80) # Adjusted position

        # Menu button
        menu_btn = lv.button(self.screen)
        menu_btn.set_size(75, 35)
        menu_btn.set_pos(right_panel_x, 105) # Adjusted position
        menu_btn.add_event_cb(self.show_menu, lv.EVENT.CLICKED, None)
        menu_label = lv.label(menu_btn)
        menu_label.set_text(lv.SYMBOL.SETTINGS + " Menu")
        menu_label.set_style_text_font(lv.font_montserrat_12, 0)
        menu_label.center()
        self._add_focus_style(menu_btn)

        # Reset button (quick access)
        reset_btn = lv.button(self.screen)
        reset_btn.set_size(75, 35)
        reset_btn.set_pos(right_panel_x, 150) # Adjusted position
        reset_btn.add_event_cb(self.on_reset, lv.EVENT.CLICKED, None)
        reset_label = lv.label(reset_btn)
        reset_label.set_text(lv.SYMBOL.REFRESH + " Reset")
        reset_label.set_style_text_font(lv.font_montserrat_12, 0)
        reset_label.center()
        self._add_focus_style(reset_btn)

        # New game button (quick access)
        new_btn = lv.button(self.screen)
        new_btn.set_size(75, 35)
        new_btn.set_pos(right_panel_x, 195) # Adjusted position
        new_btn.add_event_cb(self.on_new_game, lv.EVENT.CLICKED, None)
        new_label = lv.label(new_btn)
        new_label.set_text(lv.SYMBOL.PLUS + " New")
        new_label.center()
        self._add_focus_style(new_btn)

    def _create_info_panel_labels(self, parent):
        # Timer
        self.time_label = lv.label(parent)
        self.time_label.set_text("0:00")
        self.time_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        self.time_label.set_style_text_font(lv.font_montserrat_14, 0)
        self.time_label.align(lv.ALIGN.TOP_MID, 0, 0)

        # Moves counter
        self.moves_label = lv.label(parent)
        self.moves_label.set_text("Moves\n0")
        self.moves_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        self.moves_label.set_style_text_font(lv.font_montserrat_12, 0)
        self.moves_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.moves_label.align(lv.ALIGN.TOP_MID, 0, 25)

    def _create_win_label(self, grid_container):
        # Create a container for the win label with a background
        self.win_panel_container = lv.obj(self.screen)
        self.win_panel_container.set_size(200, 140) # Adjust size as needed
        self.win_panel_container.align_to(grid_container, lv.ALIGN.CENTER, 0, 0) # Centered on grid container
        self.win_panel_container.set_style_bg_color(lv.color_hex(self.wood_bg_color), 0)  # Wooden plank color
        self.win_panel_container.set_style_border_color(lv.color_hex(self.wood_border_color), 0)
        self.win_panel_container.set_style_radius(10, 0)
        self.win_panel_container.set_style_pad_all(10, 0)
        self.win_panel_container.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.win_panel_container.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        self.win_panel_container.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.win_panel_container.remove_flag(lv.obj.FLAG.SCROLLABLE)
        self.win_panel_container.add_flag(lv.obj.FLAG.HIDDEN) # Hidden initially

        # Win message (hidden initially)
        self.win_label = lv.label(self.win_panel_container)
        self.win_label.set_text("You Win!")
        self.win_label.set_style_text_font(lv.font_montserrat_28_compressed, 0)
        self.win_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        self.win_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.win_label.align(lv.ALIGN.CENTER, 0, 0)

    def _create_info_panel_container(self, right_panel_x):
        self.info_panel_container = lv.obj(self.screen)
        self.info_panel_container.set_size(self.RIGHT_PANEL_WIDTH, 70) # Adjusted size
        self.info_panel_container.set_pos(right_panel_x, 5)
        self.info_panel_container.set_style_bg_color(lv.color_hex(self.wood_bg_color), 0)  # Wooden plank color
        self.info_panel_container.set_style_border_color(lv.color_hex(self.wood_border_color), 0)
        self.info_panel_container.set_style_radius(5, 0)
        self.info_panel_container.set_style_pad_all(5, 0)
        self.info_panel_container.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.info_panel_container.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.START)
        self.info_panel_container.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.info_panel_container.remove_flag(lv.obj.FLAG.SCROLLABLE)

    def show_menu(self, event):
        """Show menu popup"""
        if self.menu_modal:
            return

        # Create modal background
        self.menu_modal = lv.obj(lv.layer_top())
        self.menu_modal.set_size(self.SCREEN_WIDTH, self.SCREEN_HEIGHT)
        self.menu_modal.set_style_bg_color(lv.color_hex(0x000000), 0)
        self.menu_modal.set_style_bg_opa(150, 0)
        self.menu_modal.set_style_border_width(0, 0)
        self.menu_modal.set_pos(0, 0)

        # Create menu container
        menu = lv.obj(self.menu_modal)
        menu.set_size(200, 230)
        menu.set_style_bg_color(lv.color_hex(0x34495E), 0)
        menu.set_style_radius(10, 0)
        menu.set_style_pad_all(15, 0)
        menu.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        menu.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        menu.center()

        # Create a focus group for menu buttons
        focusgroup = lv.group_get_default()

        # Title
        title = lv.label(menu)
        title.set_text("Menu")
        title.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        title.set_style_text_font(lv.font_montserrat_16, 0)

        # Grid size selector
        size_label = lv.label(menu)
        size_label.set_text(f"Grid: {self.grid_size}x{self.grid_size}")
        size_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        size_label.set_style_text_font(lv.font_montserrat_12, 0)

        # Size buttons container
        size_container = lv.obj(menu)
        size_container.set_size(lv.pct(90), 40) # Adjusted width
        size_container.set_style_bg_opa(0, 0)
        size_container.set_flex_flow(lv.FLEX_FLOW.ROW)
        size_container.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        size_container.set_style_pad_column(5, 0) # Reduced padding
        size_container.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF) # Explicitly disable scrollbar
        size_container.set_style_border_width(0,0)

        size_minus_btn = lv.button(size_container)
        size_minus_btn.set_size(40, 30) # Slightly smaller button
        size_minus_btn.add_event_cb(
            lambda e: self.change_size(-1, size_label), lv.EVENT.CLICKED, None
        )
        minus_label = lv.label(size_minus_btn)
        minus_label.set_text(lv.SYMBOL.MINUS) # Use symbol
        minus_label.center()
        self._add_focus_style(size_minus_btn)
        if focusgroup:
            focusgroup.add_obj(size_minus_btn)
            InputManager.emulate_focus_obj(focusgroup, size_minus_btn)

        size_plus_btn = lv.button(size_container)
        size_plus_btn.set_size(40, 30) # Slightly smaller button
        size_plus_btn.add_event_cb(
            lambda e: self.change_size(1, size_label), lv.EVENT.CLICKED, None
        )
        plus_label = lv.label(size_plus_btn)
        plus_label.set_text(lv.SYMBOL.PLUS) # Use symbol
        plus_label.center()
        self._add_focus_style(size_plus_btn)
        if focusgroup:
            focusgroup.add_obj(size_plus_btn)

        # New game button
        new_btn = lv.button(menu)
        new_btn.set_size(lv.pct(100), 35)
        new_btn.add_event_cb(
            lambda e: (self.on_new_game(e), self.close_menu()), lv.EVENT.CLICKED, None
        )
        new_label = lv.label(new_btn)
        new_label.set_text(lv.SYMBOL.PLUS + " New Game")
        new_label.center()
        self._add_focus_style(new_btn)
        if focusgroup:
            focusgroup.add_obj(new_btn)

        # Close button
        close_btn = lv.button(menu)
        close_btn.set_size(lv.pct(100), 35)
        close_btn.add_event_cb(lambda e: self.close_menu(), lv.EVENT.CLICKED, None)
        close_label = lv.label(close_btn)
        close_label.set_text("Close")
        close_label.center()
        self._add_focus_style(close_btn)
        if focusgroup:
            focusgroup.add_obj(close_btn)

    def change_size(self, delta, label):
        """Change grid size from menu"""
        new_size = self.grid_size + delta
        if self.MIN_GRID_SIZE <= new_size <= self.MAX_GRID_SIZE:
            self.grid_size = new_size
            label.set_text(f"Grid: {self.grid_size}x{self.grid_size}")
            label.align(lv.ALIGN.TOP_MID, 0, 40)

            # Save preference
            editor = SharedPreferences("com.quasikili.quasiboats").edit()
            editor.put_int("grid_size", self.grid_size)
            editor.commit()

    def close_menu(self):
        """Close menu and recreate grid if size changed"""
        if self.menu_modal:
            # Check if grid size changed
            old_cell_size = self.cell_size
            self.calculate_cell_size()

            if old_cell_size != self.cell_size:
                # Grid size changed - recreate
                self.recreate_grid()

            self.menu_modal.delete()
            self.menu_modal = None

    def new_game(self, seed=None):
        """Generate a new random puzzle and ensure it's solvable"""
        if seed is None:
            seed = random.randint(1, 999999)

        self.current_seed = seed
        self.seed_label.set_text(f"#{seed}")

        random.seed(seed)

        # Generate puzzle with solvability check
        max_gen_attempts = 5
        for gen_attempt in range(max_gen_attempts):
            # Clear existing boats
            for boat in self.boats:
                if boat.img:
                    boat.img.delete()
            self.boats = []
            self.selected_boat = None
            self.dragging_boat = None

            # Generate puzzle
            self.exit_row = self.grid_size // 2

            # Create player boat
            player_col = random.randint(0, max(0, self.grid_size - 2)) # Player boat is always length 2
            self.player_boat = Boat(self.exit_row, player_col, 2, True, True, "red")
            self.boats.append(self.player_boat)

            # Generate obstacle yachts
            num_obstacles = min(self.grid_size + 1, 10)
            # Only use white yachts
            colors = ["white"]

            attempts = 0
            max_attempts = 200
            while len(self.boats) < num_obstacles and attempts < max_attempts:
                attempts += 1
                # Only use lengths 2 and 3 for yachts
                length = random.choice([2, 3])
                is_horizontal = random.choice([True, False])
                color = random.choice(colors)

                if is_horizontal:
                    col = random.randint(0, self.grid_size - length)
                    row = random.randint(0, self.grid_size - 1)
                else:
                    col = random.randint(0, self.grid_size - 1)
                    row = random.randint(0, self.grid_size - length)

                new_boat = Boat(row, col, length, is_horizontal, False, color)
                new_cells = set(new_boat.get_cells())
                overlaps = False
                for existing in self.boats:
                    if new_cells & set(existing.get_cells()):
                        overlaps = True
                        break
                if not overlaps:
                    self.boats.append(new_boat)
            
            # Check solvability
            if self.is_solvable(self.boats, self.grid_size, self.exit_row):
                break
            # If not solvable and it was the last attempt, we keep it anyway but log it
            if gen_attempt == max_gen_attempts - 1:
                print("Warning: Could not guarantee solvability after 5 attempts")

        # Reset counters
        self.move_count = 0
        self.start_time = time.ticks_ms()
        self.game_won = False
        self.moves_label.set_text("Moves\n0")
        self.win_panel_container.add_flag(lv.obj.FLAG.HIDDEN)

        # Create images for boats
        self.create_boat_images()

        print(
            f"New game: seed {seed}, {len(self.boats)} boats, cell_size {self.cell_size}"
        )

    def create_boat_images(self):
        """Create LVGL images for all boats"""
        focusgroup = lv.group_get_default()

        for boat in self.boats:
            if boat.is_player:
                # Player boat is always length 2, load horizontal asset
                src = f"{self.ASSET_PATH}player_h2.png"
            else:
                # Yachts are length 2 or 3, and always white, load horizontal asset
                src = f"{self.ASSET_PATH}yacht_white_h{boat.length}.png"

            img = lv.image(self.grid_container)
            img.set_src(src)

            # Scale image to fit cell size (assets are 40px)
            scale = (self.cell_size * 256) // 40
            img.set_scale(scale)

            # Set initial position
            x = boat.col * self.cell_size
            y = boat.row * self.cell_size

            if boat.is_horizontal:
                img.set_size(boat.length * self.cell_size, self.cell_size)
                img.set_pos(x, y)
            else:
                # For vertical boats: set the image object's bounding box to vertical dimensions.
                img.set_size(self.cell_size, boat.length * self.cell_size)
                # Set the pivot to the center of this new, vertical bounding box.
                # img.set_pivot(self.cell_size // 2, (boat.length * self.cell_size) // 2)
                # Rotate the image content by 90 degrees clockwise.
                img.set_rotation(900) # LVGL uses tenths of a degree
                # Set the position of the top-left corner of this new, vertical bounding box.
                img.set_pos(x, y)


            # Make draggable and focusable
            img.add_flag(lv.obj.FLAG.CLICKABLE)
            img.add_event_cb(
                lambda e, b=boat: self.on_boat_pressed(e, b), lv.EVENT.PRESSED, None
            )
            img.add_event_cb(
                lambda e, b=boat: self.on_boat_pressing(e, b), lv.EVENT.PRESSING, None
            )
            img.add_event_cb(
                lambda e, b=boat: self.on_boat_released(e, b), lv.EVENT.RELEASED, None
            )
            img.add_event_cb(
                lambda e, b=boat: self.on_boat_focused(e, b), lv.EVENT.FOCUSED, None
            )
            img.add_event_cb(
                lambda e, b=boat: self.on_boat_defocused(e, b), lv.EVENT.DEFOCUSED, None
            )
            img.add_event_cb(
                lambda e, b=boat: self.on_boat_key(e, b), lv.EVENT.KEY, None
            ) # Add key event handler to boat

            if focusgroup:
                focusgroup.add_obj(img)

            boat.img = img

    def on_boat_key(self, event, boat):
        """Handle key events for individual boats"""
        key = event.get_key()
        print(f"on_boat_key: Key {key} pressed for boat at ({boat.row}, {boat.col}), move_locked: {self.move_locked}")
        if key == lv.KEY.ENTER or key == ord("A") or key == ord("a"):
            # First, set the editing mode based on the *new* move_locked state
            new_move_locked_state = not self.move_locked
            lv.group_get_default().set_editing(new_move_locked_state)
            
            # Then, toggle the move_locked state
            self.move_locked = new_move_locked_state
            
            self._update_boat_drag_visuals(boat)
            print(f"on_boat_key: move_locked toggled to {self.move_locked}")
            event.stop_bubbling() # Stop event from propagating to screen
            return
        
        if self.move_locked:
            if key == lv.KEY.UP:
                self.move_selected_boat("up")
                InputManager.emulate_focus_obj(lv.group_get_default(), boat.img) # Re-focus the boat after moving
                event.stop_bubbling()
            elif key == lv.KEY.DOWN:
                self.move_selected_boat("down")
                InputManager.emulate_focus_obj(lv.group_get_default(), boat.img) # Re-focus the boat after moving
                event.stop_bubbling()
            elif key == lv.KEY.LEFT:
                self.move_selected_boat("left")
                InputManager.emulate_focus_obj(lv.group_get_default(), boat.img) # Re-focus the boat after moving
                event.stop_bubbling()
            elif key == lv.KEY.RIGHT:
                self.move_selected_boat("right")
                InputManager.emulate_focus_obj(lv.group_get_default(), boat.img) # Re-focus the boat after moving
                event.stop_bubbling()
        # If not move_locked, let the event bubble up for focus navigation (no else needed)

    def on_boat_focused(self, event, boat):
        """Highlight boat when focused with keyboard"""
        print(f"on_boat_focused: Boat at ({boat.row}, {boat.col}) focused")
        self.selected_boat = boat
        boat.selected = True
        # Update visuals based on current move_locked state
        self._update_boat_drag_visuals(boat)

    def on_boat_defocused(self, event, boat):
        """Remove highlight when focus lost"""
        print(f"on_boat_defocused: Boat at ({boat.row}, {boat.col}) defocused")
        # If move_locked is True, we want the boat to remain visually focused.
        # Do not clear visuals or change editing mode.
        if self.move_locked:
            return
        
        boat.selected = False
        self.clear_drag_dots()
        boat.img.set_style_outline_width(0, 0)
        # The editing mode is managed by on_boat_key when move_locked changes.

    def on_boat_pressed(self, event, boat):
        """Handle boat press start (touch)"""
        if self.game_won:
            return

        self.selected_boat = boat
        self.dragging_boat = boat
        boat.drag_start_row = boat.row
        boat.drag_start_col = boat.col

        # Visual feedback
        boat.img.set_style_outline_width(3, 0)
        boat.img.set_style_outline_color(lv.color_hex(0xF39C12), 0)
        self._update_boat_drag_visuals(boat) # Show dots on press

    def on_boat_pressing(self, event, boat):
        """Handle boat dragging (touch)"""
        # Only process if actually dragging with touch, not just holding Enter
        if not self.dragging_boat or self.game_won or self.move_locked:
            return

        # Get touch position relative to grid
        indev = lv.indev_active()
        point = lv.point_t()
        indev.get_point(point)

        # Convert to grid coordinates
        grid_x = point.x - self.grid_offset_x
        grid_y = point.y - self.grid_offset_y

        new_col = grid_x // self.cell_size
        new_row = grid_y // self.cell_size

        # Constrain movement to boat's orientation
        if boat.is_horizontal:
            new_row = boat.row  # Lock row
        else:
            new_col = boat.col  # Lock column

        # Clamp to grid bounds
        new_row = max(0, min(new_row, self.grid_size - 1))
        if boat.is_horizontal:
            new_col = max(0, min(new_col, self.grid_size - boat.length))
        else:
            new_col = max(0, min(new_col, self.grid_size - 1))

        # Check if valid move (prevents passing through other boats)
        if boat.can_move_to(new_row, new_col, self.grid_size, self.boats):
            # Update boat position in model
            boat.row = new_row
            boat.col = new_col
            
            # Update visual position
            x = new_col * self.cell_size
            y = new_row * self.cell_size
            boat.img.set_pos(x, y)
            self._update_boat_drag_visuals(boat) # Update dots during dragging

    def on_boat_released(self, event, boat):
        """Handle boat release - snap to grid (touch)"""
        if not self.dragging_boat or self.game_won:
            return

        # Get current position
        x = boat.img.get_x()
        y = boat.img.get_y()

        # Snap to grid
        new_col = round(x / self.cell_size)
        new_row = round(y / self.cell_size)

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
                self.moves_label.set_text(f"Moves\n{self.move_count}")

                # Check win condition
                if (
                    boat.is_player
                    and boat.row == self.exit_row
                    and boat.col + boat.length >= self.grid_size
                ):
                    self.on_win()
        else:
            # Invalid position - snap back to start
            new_row = boat.drag_start_row
            new_col = boat.drag_start_col
            boat.row = new_row
            boat.col = new_col

        # Snap to grid visually
        x = new_col * self.cell_size
        y = new_row * self.cell_size
        boat.img.set_pos(x, y)

        # Update visual feedback
        self._update_boat_drag_visuals(boat)

        self.dragging_boat = None
        self._update_boat_drag_visuals(boat) # Clear dots on release

    def move_selected_boat(self, direction):
        """Move selected boat with keyboard (only when Enter/A is held)"""
        print(f"move_selected_boat: Direction {direction}, move_locked: {self.move_locked}")
        if not self.selected_boat or self.game_won or not self.move_locked:
            print("move_selected_boat: Conditions not met for movement")
            return

        boat = self.selected_boat
        new_row = boat.row
        new_col = boat.col

        if direction == "up" and not boat.is_horizontal:
            new_row -= 1
        elif direction == "down" and not boat.is_horizontal:
            new_row += 1
        elif direction == "left" and boat.is_horizontal:
            new_col -= 1
        elif direction == "right" and boat.is_horizontal:
            new_col += 1
        else:
            return

        if boat.can_move_to(new_row, new_col, self.grid_size, self.boats):
            boat.row = new_row
            boat.col = new_col

            x = new_col * self.cell_size
            y = new_row * self.cell_size
            boat.img.set_pos(x, y)

            self.move_count += 1
            self.moves_label.set_text(f"Moves\n{self.move_count}")

            if (
                boat.is_player
                and boat.row == self.exit_row
                and boat.col + boat.length >= self.grid_size
            ):
                self.on_win()

    def on_win(self):
        """Handle winning the puzzle"""
        self.game_won = True
        elapsed = time.ticks_diff(time.ticks_ms(), self.start_time) // 1000

        minutes = elapsed // 60
        seconds = elapsed % 60

        self.win_label.set_text(
            f"You Win!\n{self.move_count} moves\n{minutes}:{seconds:02d}"
        )
        self.win_panel_container.remove_flag(lv.obj.FLAG.HIDDEN)

        print(f"Puzzle solved! Moves: {self.move_count}, Time: {elapsed}s")

    def on_reset(self, event):
        """Reset current puzzle"""
        self.new_game(self.current_seed)

    def on_new_game(self, event):
        """Start new random puzzle"""
        self.new_game()

    def recreate_grid(self):
        """Recreate the grid with new size"""
        # Delete old containers
        if self.grid_container:
            self.grid_container.delete()
        if self.win_panel_container:
            self.win_panel_container.delete()
        if self.info_panel_container:
            self.info_panel_container.delete()

        # Clear boat list
        self.boats = []

        # Recreate grid container with new cell size
        grid_pixel_size = self.grid_size * self.cell_size + 4

        
        self._create_grid_container(grid_pixel_size)
        self._create_exit_marker()

        # Recreate info panel container and labels
        right_panel_content_size = self.grid_size * self.cell_size
        right_panel_x = self.grid_offset_x + right_panel_content_size + 5

        self._create_info_panel_container(right_panel_x)

        self._create_info_panel_labels(self.info_panel_container)
        self._create_win_label(self.grid_container)

        # Start new game
        self.new_game()

    def _create_grid_container(self, grid_pixel_size):
        self.grid_container = lv.obj(self.screen)
        self.grid_container.set_size(grid_pixel_size, grid_pixel_size)
        self.grid_container.set_pos(self.grid_offset_x - 2, self.grid_offset_y - 2)
        self.grid_container.set_style_bg_opa(0, 0)
        self.grid_container.set_style_border_width(1, 0)
        self.grid_container.set_style_border_color(lv.color_hex(0x4C555E), 0)
        self.grid_container.set_style_border_color(lv.color_hex(0x2C3E50), 0)
        self.grid_container.set_style_pad_all(2, 0)
        self.grid_container.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.grid_container.remove_flag(lv.obj.FLAG.SCROLLABLE)

    def _create_exit_marker(self):
        """Create the exit marker and arrow label"""
        self.exit_row = self.grid_size // 2
        exit_marker = lv.obj(self.grid_container)
        hori_multiplier = 0.3
        exit_marker.set_size(int(self.cell_size*hori_multiplier), self.cell_size)
        exit_marker.set_pos(
            (self.grid_size - 1) * self.cell_size + int(self.cell_size*(1-hori_multiplier)), self.exit_row * self.cell_size
        )
        exit_marker.set_style_bg_color(lv.color_hex(self.wood_bg_color), 0)
        exit_marker.set_style_border_color(lv.color_hex(self.wood_border_color), 0)
        exit_marker.set_style_border_width(2, 0)
        # exit_marker.set_style_radius(0, 0)
        # exit_marker.set_style_border_width(4, 0)
        exit_marker.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        exit_marker.remove_flag(lv.obj.FLAG.SCROLLABLE)

        arrow_label = lv.label(self.grid_container)
        arrow_label.set_size(self.cell_size, self.cell_size)
        print(f"cell size {self.cell_size}")
        arrow_label.set_text(lv.SYMBOL.RIGHT)
        arrow_label.set_style_text_color(lv.color_hex(0xFFD700), 0)
       
        arrow_label.set_style_text_font(lv.font_montserrat_24, 0) # Increased font size
        arrow_label.set_pos(
            (self.grid_size - 1) * self.cell_size, (self.exit_row * self.cell_size) + (round((self.cell_size/2)- 13))
        )
    


    def on_key(self, event):
        """Handle keyboard input"""
        key = event.get_key()
        # Don't process game keys if menu is open
        if self.menu_modal:
            return
        # Arrow keys move boat when locked
        # Arrow keys move boat when locked (handled by boat's on_boat_key)
        elif key == ord("R") or key == ord("r"):
            self.on_reset(event)
        elif key == ord("N") or key == ord("n"):
            self.on_new_game(event)
        elif key == ord("M") or key == ord("m"):
            self.show_menu(event)

    def update_frame(self, timer):
        """Main game loop - update timer and check key state"""
        if not self.game_won:
            elapsed = time.ticks_diff(time.ticks_ms(), self.start_time) // 1000
            minutes = elapsed // 60
            seconds = elapsed % 60
            self.time_label.set_text(f"{minutes}:{seconds:02d}")

        # Check if Enter/A key is released
        # Check if Enter/A key is released (only if not handled by boat directly)
        # This is a fallback for when the boat doesn't consume the event
        indev = lv.indev_active()
        if indev and indev.get_type() == lv.INDEV_TYPE.KEYPAD:
            if not indev.get_key(): # No key is currently pressed
                if self.move_locked:
                    self.move_locked = False
                    if self.selected_boat:
                            self._update_boat_drag_visuals(self.selected_boat)

    def _update_boat_drag_visuals(self, boat):
        """Update boat visual feedback for dragging (red border, dots)"""
        print(f"_update_boat_drag_visuals: boat at ({boat.row}, {boat.col}), selected: {boat.selected}, move_locked: {self.move_locked}")
        if boat.selected:
            if self.move_locked:
                boat.img.set_style_outline_width(3, 0)
                boat.img.set_style_outline_color(lv.color_hex(0xFF0000), 0)  # Red
                self.create_drag_dots(boat)
            else:
                boat.img.set_style_outline_width(3, 0)
                boat.img.set_style_outline_color(lv.color_hex(0xFFFFFF), 0)  # White
                self.clear_drag_dots()
        else:
            boat.img.set_style_outline_width(0, 0)
            self.clear_drag_dots()

    def create_drag_dots(self, boat):
        """Create dots to indicate possible drag directions"""
        self.clear_drag_dots()

        dot_size = self.cell_size // 4
        dot_color = lv.color_hex(0xFF0000) # Red dots

        if boat.is_horizontal:
            # Left dot
            if boat.col > 0 and boat.can_move_to(boat.row, boat.col - 1, self.grid_size, self.boats):
                dot = lv.obj(self.grid_container)
                dot.set_size(dot_size, dot_size)
                dot.set_style_radius(lv.RADIUS_CIRCLE, 0)
                dot.set_style_bg_color(dot_color, 0)
                dot.align_to(boat.img, lv.ALIGN.LEFT_MID, -dot_size // 2, 0)
                self.drag_dots.append(dot)

            # Right dot
            if boat.col + boat.length < self.grid_size and boat.can_move_to(boat.row, boat.col + 1, self.grid_size, self.boats):
                dot = lv.obj(self.grid_container)
                dot.set_size(dot_size, dot_size)
                dot.set_style_radius(lv.RADIUS_CIRCLE, 0)
                dot.set_style_bg_color(dot_color, 0)
                dot.align_to(boat.img, lv.ALIGN.RIGHT_MID, dot_size // 2, 0)
                self.drag_dots.append(dot)
        else: # Vertical
            # Up dot
            if boat.row > 0 and boat.can_move_to(boat.row - 1, boat.col, self.grid_size, self.boats):
                dot = lv.obj(self.grid_container)
                dot.set_size(dot_size, dot_size)
                dot.set_style_radius(lv.RADIUS_CIRCLE, 0)
                dot.set_style_bg_color(dot_color, 0)
                dot.align_to(boat.img, lv.ALIGN.TOP_MID, 0, -dot_size // 2)
                self.drag_dots.append(dot)

            # Down dot
            if boat.row + boat.length < self.grid_size and boat.can_move_to(boat.row + 1, boat.col, self.grid_size, self.boats):
                dot = lv.obj(self.grid_container)
                dot.set_size(dot_size, dot_size)
                dot.set_style_radius(lv.RADIUS_CIRCLE, 0)
                dot.set_style_bg_color(dot_color, 0)
                dot.align_to(boat.img, lv.ALIGN.BOTTOM_MID, 0, dot_size // 2)
                self.drag_dots.append(dot)

    def clear_drag_dots(self):
        """Delete all active drag dots"""
        for dot in self.drag_dots:
            dot.delete()
        self.drag_dots = []

    def _add_focus_style(self, obj):
        """Apply a standard focus highlight to buttons"""
        obj.set_style_outline_width(2, lv.STATE.FOCUS_KEY)
        obj.set_style_outline_color(lv.color_hex(0xFFFFFF), lv.STATE.FOCUS_KEY)
        obj.set_style_outline_opa(255, lv.STATE.FOCUS_KEY)

    def is_solvable(self, boats, grid_size, exit_row):
        """Simple BFS to check if the player boat can reach the exit"""
        player_boat = boats[0]
        target_col = grid_size - player_boat.length
        start_state = tuple(b.col if b.is_horizontal else b.row for b in boats)
        queue = [start_state]
        visited = {start_state}
        max_states = 500
        head = 0
        while head < len(queue) and len(visited) < max_states:
            state = queue[head]
            head += 1
            if state[0] >= target_col:
                return True
            for i in range(len(boats)):
                curr_val = state[i]
                for step in [-1, 1]:
                    new_val = curr_val + step
                    if not self._check_collision_static(i, new_val, state, boats, grid_size):
                        new_state_list = list(state)
                        new_state_list[i] = new_val
                        new_state = tuple(new_state_list)
                        if new_state not in visited:
                            visited.add(new_state)
                            queue.append(new_state)
        return False

    def _check_collision_static(self, boat_idx, new_val, state, boats, grid_size):
        """Check collision for BFS solver (static state)"""
        b = boats[boat_idx]
        length = b.length
        is_h = b.is_horizontal
        r1 = b.row if is_h else new_val
        c1 = new_val if is_h else b.col
        if new_val < 0 or new_val + length > grid_size:
            return True
        for j in range(len(boats)):
            if boat_idx == j: continue
            bj = boats[j]
            vj = state[j]
            is_hj = bj.is_horizontal
            r2 = bj.row if is_hj else vj
            c2 = vj if is_hj else bj.col
            l2 = bj.length
            if is_h == is_hj:
                if (r1 == r2 if is_h else c1 == c2):
                    start1, start2 = (c1 if is_h else r1), (c2 if is_hj else r2)
                    if start1 < start2 + l2 and start2 < start1 + length:
                        return True
            else:
                rh, ch, lh = (r1 if is_h else r2), (c1 if is_h else c2), (length if is_h else l2)
                rv, cv, lv = (r2 if not is_hj else r1), (c2 if not is_hj else c1), (l2 if not is_hj else length)
                if rv <= rh < rv + lv and ch <= cv < ch + lh:
                    return True
        return False

    def onResume(self, screen):
        """Activity goes foreground"""
        self.update_timer = lv.timer_create(self.update_frame, 16, None) # max 60 fps = 16ms/frame

    def onPause(self, screen):
        """Activity goes background"""
        # Delete the timer
        if self.update_timer:
            self.update_timer.delete()
            self.update_timer = None

