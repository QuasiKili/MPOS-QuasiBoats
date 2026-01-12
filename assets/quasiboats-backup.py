import time
import random

from mpos.apps import Activity
import mpos.ui
import mpos.config
from mpos.ui.focus_direction import emulate_focus_obj

try:
    import lvgl as lv # pyright: ignore[reportMissingModuleSource]
except ImportError:
    pass  # lv is already available as a global in MicroPython OS


class Pipe:
    """Represents a single pipe obstacle"""

    def __init__(self, x, gap_y, gap_size=60):
        self.x = x
        self.gap_y = gap_y
        self.gap_size = gap_size
        self.width = 40
        self.passed = False


class Boat:
    def __init__(self, width, height, x, y, movementAxis, isPlayer):
        self.width = width
        self.height = 


class QuasiBoats(Activity):
    # Asset path
    ASSET_PATH = "M:apps/com.quasikili.quasiboats/assets/"

    # Screen dimensions
    SCREEN_WIDTH = 320
    SCREEN_HEIGHT = 240

    # Game physics constants
    GRAVITY = 200  # pixels per second^2
    FLAP_VELOCITY = -50  # pixels per second
    BIRD_X = 60  # Fixed X position

    # Bird properties
    bird_y = 120
    bird_velocity = 0
    bird_size = 32
    bird_overlap = 6 # Only collide when there's enough overlap - real birds also don't die from brushing against something ;-)

    # Pipe properties
    PIPE_IMAGE_HEIGHT = 200
    PIPE_SPEED = 100  # pixels per second
    PIPE_SPAWN_DISTANCE = 200
    PIPE_GAP_SIZE = 80
    PIPE_MIN_Y = 20
    PIPE_MAX_Y = SCREEN_HEIGHT - 120
    pipes = []

    # Cloud properties (parallax effect)
    CLOUD_SPEED = 30  # pixels per second (slower than pipes for depth)
    cloud_images = []
    cloud_positions = []

    # Ground properties
    GROUND_HEIGHT = 40

    # Game state
    score = 0
    highscore = 0
    game_over = False
    game_started = False
    is_fire_bird = False  # Track if we're using the fire bird
    show_fps = 0 # 0 means off, 1 means current, 2 means average
    game_paused = False  # Track if game is paused
    popup_modal = None  # Reference to popup modal background

    # Timing for framerate independence
    last_time = 0

    # UI Elements
    screen = None
    bird_img = None
    pipe_images = []
    MAX_PIPES = 4  # Maximum number of pipe pairs to display
    ground_img = None
    ground_x = 0
    score_label = None
    score_bg = None
    highscore_label = None
    highscore_bg = None
    game_over_label = None
    start_label = None
    avg_fps = 0
    last_fps = 0  # To store the latest FPS value
    fps_label = None
    fps_bg = None

    def onCreate(self):
        print("Quasi Boats starting...")

        # Load highscore from persistent storage
        print("Loading preferences...")
        prefs = mpos.config.SharedPreferences("com.quasikili.quasiboats")
        self.highscore = prefs.get_int("highscore", 0)
        print(f"Loaded highscore: {self.highscore}")

        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_hex(0x87CEEB), 0)  # Sky blue
        self.screen.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.screen.remove_flag(lv.obj.FLAG.SCROLLABLE)  # Disable scrolling completely

        # Make screen focusable for keyboard input
        focusgroup = lv.group_get_default()
        if focusgroup:
            focusgroup.add_obj(self.screen)

        # Event handlers
        self.screen.add_event_cb(self.on_tap, lv.EVENT.CLICKED, None)
        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)

        # Create ground (will be scrolling with tiling)
        self.ground_img = lv.image(self.screen)
        self.ground_img.set_src(f"{self.ASSET_PATH}ground.png")
        self.ground_img.set_size(self.SCREEN_WIDTH, self.GROUND_HEIGHT)  # Set size larger than image

        self.ground_img.set_inner_align(lv.image.ALIGN.TILE)
        self.ground_img.set_pos(0, self.SCREEN_HEIGHT - self.GROUND_HEIGHT)

        # Create clouds for parallax scrolling (behind bird, in front of sky)
        cloud_start_positions = [
            ( 50, 30),  # Cloud 1: top right
            ( 180, 60),  # Cloud 2: middle right
            ( 320, 40),  # Cloud 3: far right
        ]
        for x, y in cloud_start_positions:
            cloud = lv.image(self.screen)
            cloud.set_src(f"{self.ASSET_PATH}cloud.png")
            cloud.set_pos(x, y)
            self.cloud_images.append(cloud)
            self.cloud_positions.append(x)

        # Create bird
        self.bird_img = lv.image(self.screen)
        self.bird_img.set_src(f"{self.ASSET_PATH}bird.png")
        self.bird_img.set_pos(self.BIRD_X, int(self.bird_y))

        # Create pipe image pool (pre-create all pipe images)
        for i in range(self.MAX_PIPES):
            # Top pipe (flipped using style transform)
            top_pipe = lv.image(self.screen)
            top_pipe.set_src(f"{self.ASSET_PATH}pipe.png")
            # transform image object this way to rotate
            top_pipe.set_rotation(1800)  # 180 degrees * 10

            # Alternative: use style transform rotation for 180 degree flip and pivot
            # top_pipe.set_style_transform_rotation(1800, 0)  # 180 degrees * 10
            # top_pipe.set_style_transform_pivot_x(20, 0)  # Center X (pipe is 40px wide)
            # top_pipe.set_style_transform_pivot_y(100, 0)  # Center Y (pipe is 200px tall)

            # you can also set width to stretch the image
            # top_pipe.set_width(200)
            # top_pipe.set_inner_align(lv.image.ALIGN.STRETCH)
            top_pipe.add_flag(lv.obj.FLAG.HIDDEN)  # Start hidden

            # Bottom pipe
            bottom_pipe = lv.image(self.screen)
            bottom_pipe.set_src(f"{self.ASSET_PATH}pipe.png")
            bottom_pipe.add_flag(lv.obj.FLAG.HIDDEN)  # Start hidden

            self.pipe_images.append(
                {"top": top_pipe, "bottom": bottom_pipe, "in_use": False}
            )

        # Create score display (top right, with frame background)
        self.score_bg = lv.obj(self.screen)
        self.score_bg.set_size(60, 35)
        self.score_bg.set_style_bg_color(lv.color_hex(0x000000), 0)  # Black background
        self.score_bg.set_style_bg_opa(180, 0)  # Semi-transparent
        self.score_bg.set_style_border_color(lv.color_hex(0xFFFFFF), 0)  # White border
        self.score_bg.set_style_border_width(2, 0)
        self.score_bg.set_style_radius(8, 0)  # Rounded corners
        self.score_bg.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)  # Disable scrollbar
        self.score_bg.align(lv.ALIGN.TOP_RIGHT, -10, 10)
        self.score_label = lv.label(self.score_bg)
        self.score_label.set_text("0")
        self.score_label.set_style_text_font(lv.font_montserrat_28_compressed, 0)
        self.score_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        self.score_label.center()

        # Create highscore display (top left, with frame background)
        self.highscore_bg = lv.obj(self.screen)
        self.highscore_bg.set_size(60, 35)
        self.highscore_bg.set_style_bg_color(lv.color_hex(0x000000), 0)  # Black background
        self.highscore_bg.set_style_bg_opa(180, 0)  # Semi-transparent
        self.highscore_bg.set_style_border_color(lv.color_hex(0xFFD700), 0)  # Gold border
        self.highscore_bg.set_style_border_width(2, 0)
        self.highscore_bg.set_style_radius(8, 0)  # Rounded corners
        self.highscore_bg.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)  # Disable scrollbar
        self.highscore_bg.align(lv.ALIGN.TOP_LEFT, 10, 10)
        self.highscore_bg.add_flag(lv.obj.FLAG.CLICKABLE)  # Make it clickable
        self.highscore_bg.add_event_cb(self.on_highscore_tap, lv.EVENT.CLICKED, None)
        self.highscore_label = lv.label(self.highscore_bg)
        self.highscore_label.set_text(f"Hi:{self.highscore}")
        self.highscore_label.set_style_text_font(lv.font_montserrat_20, 0)
        self.highscore_label.set_style_text_color(lv.color_hex(0xFFD700), 0)  # Gold text
        self.highscore_label.center()

        # Create FPS  display (bottom left, with frame background)
        self.fps_bg = lv.obj(self.screen)
        self.fps_bg.set_size(55, 20)
        self.fps_bg.set_style_bg_color(lv.color_hex(0x000000), 0)  # Black background
        self.fps_bg.set_style_bg_opa(180, 0)  # Semi-transparent
        self.fps_bg.set_style_border_color(lv.color_hex(0xFFFFFF), 0)  # White border
        self.fps_bg.set_style_border_width(2, 0)
        self.fps_bg.set_style_radius(8, 0)  # Rounded corners
        self.fps_bg.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)  # Disable scrollbar
        self.fps_bg.align(lv.ALIGN.BOTTOM_LEFT, 8, -8)
        self.fps_bg.add_flag(lv.obj.FLAG.HIDDEN)
        self.fps_bg.remove_flag(lv.obj.FLAG.CLICKABLE)  # Allow clicks to pass through to screen
        self.fps_label = lv.label(self.fps_bg)
        self.fps_label.set_text("0 FPS")
        self.fps_label.set_style_text_font(lv.font_montserrat_12, 0)
        self.fps_label.set_style_text_color(lv.color_hex(0x00FF00), 0)
        self.fps_label.center()

        # Create start instruction label
        self.start_label = lv.label(self.screen)
        helptext = "Tap to start!\n\nTop left to reset high score,\nbottom left to show FPS."
        if "fri3d" in mpos.info.get_hardware_id():
            helptext = "Press A to start!\n\nY to reset high score,\nB to show FPS."
        self.start_label.set_text(helptext)
        self.start_label.set_style_text_font(lv.font_montserrat_20, 0)
        self.start_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        self.start_label.align(lv.ALIGN.CENTER, 0, 0)

        # Create game over label (hidden initially)
        self.game_over_label = lv.label(self.screen)
        self.game_over_label.set_text("Game Over!\nTap to Restart")
        self.game_over_label.set_style_text_font(lv.font_montserrat_20, 0)
        self.game_over_label.set_style_text_color(lv.color_hex(0xFF0000), 0)
        self.game_over_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.game_over_label.align(lv.ALIGN.CENTER, 0, 0)
        self.game_over_label.add_flag(lv.obj.FLAG.HIDDEN)

        self.setContentView(self.screen)
        print("Quasi Bird created")

    def onResume(self, screen): # Activity goes foreground
        lv.log_register_print_cb(self.log_callback)
        mpos.ui.task_handler.add_event_cb(self.update_frame, 1)

    def onPause(self, screen): # Activity goes background
        mpos.ui.task_handler.remove_event_cb(self.update_frame)
        lv.log_register_print_cb(None)

    def on_tap(self, event):
        """Handle tap/click events"""
        # Get tap coordinates
        tap_x, tap_y = mpos.ui.get_pointer_xy()

        # Check if tap is in the FPS area (bottom left corner)
        # FPS background is 55x20 at position (8, SCREEN_HEIGHT - 8 - 20)
        fps_left = 8
        fps_right = 8 + 55
        fps_top = self.SCREEN_HEIGHT - 8 - 20
        fps_bottom = self.SCREEN_HEIGHT - 8

        if (fps_left <= tap_x <= fps_right and fps_top <= tap_y <= fps_bottom):
            # Toggle FPS display
            self.toggle_fps()

        # Always handle the tap as a normal game action
        if not self.game_started:
            self.start_game()
        elif self.game_over:
            self.restart_game()
        else:
            self.flap()

    def toggle_fps(self):
        """Toggle FPS display between off, current FPS, and average FPS"""
        self.show_fps += 1
        if self.show_fps > 2:
            self.show_fps = 0
        if self.show_fps > 0:
            self.fps_bg.remove_flag(lv.obj.FLAG.HIDDEN)
        else:
            self.fps_bg.add_flag(lv.obj.FLAG.HIDDEN)

    def on_key(self, event):
        """Handle keyboard input"""
        key = event.get_key()
        if key == lv.KEY.ENTER or key == lv.KEY.UP:
            if not self.game_started:
                self.start_game()
            elif self.game_over:
                self.restart_game()
            else:
                self.flap()
        elif key == ord("B") or key == ord("b"):
            self.toggle_fps()
        elif key == ord("Y") or key == ord("y"):
            self.on_highscore_tap(event)
        else:
            print(f"on_key: unhandled key {key}")

    def on_highscore_tap(self, event):
        """Handle tap on highscore label"""
        if self.game_started and not self.game_over:
            # Pause the game
            self.game_paused = True

        # Show popup asking to delete highscore
        self.show_delete_highscore_popup()

    def show_delete_highscore_popup(self):
        """Show a popup asking if user wants to delete highscore"""
        # Create modal background (semi-transparent overlay)
        self.popup_modal = lv.obj(lv.layer_top())
        self.popup_modal.set_size(self.SCREEN_WIDTH, self.SCREEN_HEIGHT)
        self.popup_modal.set_style_bg_color(lv.color_hex(0x000000), 0)
        self.popup_modal.set_style_bg_opa(150, 0)  # Semi-transparent
        self.popup_modal.set_style_border_width(0, 0)
        self.popup_modal.set_pos(0, 0)

        # Create popup container
        popup = lv.obj(self.popup_modal)
        popup.set_size(200, 120)
        popup.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)
        popup.set_style_border_color(lv.color_hex(0x000000), 0)
        popup.set_style_border_width(3, 0)
        popup.set_style_radius(10, 0)
        popup.center()

        # Create question label
        question = lv.label(popup)
        question.set_text("Delete high score?")
        question.set_style_text_color(lv.color_hex(0x000000), 0)
        question.set_style_text_font(lv.font_montserrat_16, 0)
        question.align(lv.ALIGN.TOP_MID, 0, 15)

        # Create Yes button
        yes_btn = lv.button(popup)
        yes_btn.set_size(75, 35)
        yes_btn.align(lv.ALIGN.BOTTOM_LEFT, 0, 0)
        yes_btn.add_event_cb(self.on_delete_yes, lv.EVENT.CLICKED, None)
        yes_label = lv.label(yes_btn)
        yes_label.set_text("Yes")
        yes_label.center()

        # Create No button
        no_btn = lv.button(popup)
        no_btn.set_size(75, 35)
        no_btn.align(lv.ALIGN.BOTTOM_RIGHT, 0, 0)
        no_btn.add_event_cb(self.on_delete_no, lv.EVENT.CLICKED, None)
        no_label = lv.label(no_btn)
        no_label.set_text("No")
        no_label.center()

        # Add buttons to focus group and set focus on "No" button
        focusgroup = lv.group_get_default()
        if focusgroup:
            focusgroup.add_obj(yes_btn)
            focusgroup.add_obj(no_btn)
            # Set focus on the "No" button by default
            emulate_focus_obj(focusgroup, no_btn)

    def on_delete_yes(self, event):
        """Handle Yes button - delete highscore"""
        # Reset highscore to 0
        self.highscore = 0
        self.highscore_label.set_text(f"Hi:{self.highscore}")
        self.highscore_label.center()

        # Save to persistent storage
        print("Highscore deleted, saving...")
        editor = mpos.config.SharedPreferences("com.quasikili.quasibird").edit()
        editor.put_int("highscore", 0)
        editor.commit()

        # Close popup and unpause
        self.close_popup()

    def on_delete_no(self, event):
        """Handle No button - cancel"""
        # Just close popup and unpause
        self.close_popup()

    def close_popup(self):
        """Close the popup and unpause the game"""
        # Delete modal (this also removes buttons from focus group automatically)
        if self.popup_modal:
            self.popup_modal.delete()
            self.popup_modal = None

        # Refocus on the screen
        focusgroup = lv.group_get_default()
        if focusgroup:
            emulate_focus_obj(focusgroup, self.screen)

        # Unpause game
        self.game_paused = False

        # Reset last_time to avoid large delta after unpause
        self.last_time = time.ticks_ms()

    def start_game(self):
        """Initialize game state"""
        self.game_started = True
        self.game_over = False
        self.game_paused = False
        self.score = 0
        self.is_fire_bird = False  # Reset to normal bird

        # Switch back to normal bird sprite
        self.bird_img.set_src(f"{self.ASSET_PATH}bird.png")

        self.score_label.set_text(str(self.score))
        self.bird_y = self.SCREEN_HEIGHT / 2
        self.bird_velocity = 0
        self.pipes = []
        self.last_time = time.ticks_ms()

        # Hide start label
        self.start_label.add_flag(lv.obj.FLAG.HIDDEN)

        # Hide all pipe images
        for pipe_img in self.pipe_images:
            pipe_img["in_use"] = False
            pipe_img["top"].add_flag(lv.obj.FLAG.HIDDEN)
            pipe_img["bottom"].add_flag(lv.obj.FLAG.HIDDEN)

        # Spawn initial pipes
        for i in range(min(3, self.MAX_PIPES)):
            gap_y = random.randint(self.PIPE_MIN_Y, self.PIPE_MAX_Y)
            pipe = Pipe(
                self.SCREEN_WIDTH + i * self.PIPE_SPAWN_DISTANCE,
                gap_y,
                self.PIPE_GAP_SIZE,
            )
            self.pipes.append(pipe)

    def restart_game(self):
        """Restart after game over"""
        # Hide game over label
        self.game_over_label.add_flag(lv.obj.FLAG.HIDDEN)

        # Start new game
        self.start_game()

    def flap(self):
        """Make the bird flap"""
        if not self.game_over:
            self.bird_velocity = self.FLAP_VELOCITY

    def update_pipe_images(self):
        """Update pipe image positions and visibility"""
        # First, mark all as not in use
        for pipe_img in self.pipe_images:
            pipe_img["in_use"] = False

        # Map visible pipes to image slots
        for i, pipe in enumerate(self.pipes):
            if i < self.MAX_PIPES:
                pipe_imgs = self.pipe_images[i]
                pipe_imgs["in_use"] = True

                pipe_imgs["top"].remove_flag(lv.obj.FLAG.HIDDEN)
                pipe_imgs["top"].set_pos(int(pipe.x), int(pipe.gap_y - self.PIPE_IMAGE_HEIGHT))

                # Show and update bottom pipe
                pipe_imgs["bottom"].remove_flag(lv.obj.FLAG.HIDDEN)
                pipe_imgs["bottom"].set_pos(int(pipe.x),int(pipe.gap_y + pipe.gap_size))

        # Hide unused pipe images
        for pipe_img in self.pipe_images:
            if not pipe_img["in_use"]:
                pipe_img["top"].add_flag(lv.obj.FLAG.HIDDEN)
                pipe_img["bottom"].add_flag(lv.obj.FLAG.HIDDEN)

    def check_collision(self):
        """Check if bird collides with pipes or boundaries"""
        # Check ground and ceiling
        if self.bird_y <= 0 or self.bird_y >= self.SCREEN_HEIGHT - self.GROUND_HEIGHT - self.bird_size + self.bird_overlap:
            return True

        # Check pipe collision
        bird_left = self.BIRD_X + self.bird_overlap
        bird_right = self.BIRD_X + self.bird_size - self.bird_overlap
        bird_top = self.bird_y + self.bird_overlap
        bird_bottom = self.bird_y + self.bird_size - self.bird_overlap

        for pipe in self.pipes:
            pipe_left = pipe.x
            pipe_right = pipe.x + pipe.width

            # Check if bird is in horizontal range of pipe
            if bird_right > pipe_left and bird_left < pipe_right:
                # Check if bird is outside the gap
                if bird_top < pipe.gap_y or bird_bottom > pipe.gap_y + pipe.gap_size:
                    return True

        return False

    def update_frame(self, a, b):
        """Main game loop with framerate-independent physics"""

        current_time = time.ticks_ms()
        delta_ms = time.ticks_diff(current_time, self.last_time)
        delta_time = delta_ms / 1000.0  # Convert to seconds
        self.last_time = current_time

        if self.show_fps == 1:
            self.fps_label.set_text(f"FPS:{self.last_fps}")
        elif self.show_fps == 2:
            self.fps_label.set_text(f"FPS:{round(self.average_fps)}")

        if not self.game_started or self.game_over or self.game_paused:
            return

        # Update physics
        self.bird_velocity += self.GRAVITY * delta_time
        self.bird_y += self.bird_velocity * delta_time

        # Update bird position
        self.bird_img.set_y(int(self.bird_y))

        # Update cloud parallax scrolling (slower than pipes for depth)
        for i, cloud_img in enumerate(self.cloud_images):
            self.cloud_positions[i] -= self.CLOUD_SPEED * delta_time

            # Wrap cloud when it goes off screen
            if self.cloud_positions[i] < -60:  # Cloud width is ~50px
                self.cloud_positions[i] = self.SCREEN_WIDTH + 20

            # Update cloud position
            cloud_img.set_x(int(self.cloud_positions[i]))

        # Update pipes
        for pipe in self.pipes:
            pipe.x -= self.PIPE_SPEED * delta_time

            # Check if pipe was passed (for scoring)
            if not pipe.passed and pipe.x + pipe.width < self.BIRD_X:
                pipe.passed = True
                self.score += 1
                self.score_label.set_text(str(self.score))
                self.score_label.center()

                # Switch to fire bird when beating highscore!
                if self.score > self.highscore and not self.is_fire_bird:
                    self.is_fire_bird = True
                    print("! FIRE BIRD ACTIVATED !")
                    self.bird_img.set_src(f"{self.ASSET_PATH}fire_bird.png")

        # Remove off-screen pipes and spawn new ones
        if self.pipes and self.pipes[0].x < -self.pipes[0].width:
            # Remove the first pipe
            self.pipes.pop(0)

            # Spawn new pipe at the end
            if self.pipes:
                last_pipe = self.pipes[-1]
                gap_y = random.randint(self.PIPE_MIN_Y, self.PIPE_MAX_Y)
                new_pipe = Pipe(
                    last_pipe.x + self.PIPE_SPAWN_DISTANCE,
                    gap_y,
                    self.PIPE_GAP_SIZE,
                )
                self.pipes.append(new_pipe)

        # Update pipe image positions and visibility
        self.update_pipe_images()

        # Update ground scrolling (using tiling with offset)
        self.ground_x -= self.PIPE_SPEED * delta_time
        # No need to reset - tiling handles wrapping automatically
        self.ground_img.set_offset_x(int(self.ground_x))

        # Check collision
        if self.check_collision():
            self.game_over = True

            # Update highscore if beaten
            if self.score > self.highscore:
                self.highscore = self.score
                self.score = 0  # Reset score to avoid confusion
                self.highscore_label.set_text(f"Hi:{self.highscore}")
                self.highscore_label.center()

                # Save new highscore to persistent storage
                print(f"New highscore: {self.highscore}! Saving...")
                editor = mpos.config.SharedPreferences("com.quasikili.quasibird").edit()
                editor.put_int("highscore", self.highscore)
                editor.commit()

            self.game_over_label.remove_flag(lv.obj.FLAG.HIDDEN)

    average_samples = 20
    buffer = [0.0] * average_samples
    index = 0
    sum = 0.0
    count = 0  # Number of valid samples (0 to average_samples)
    def moving_average(self, value):
        # Subtract the value being overwritten (if buffer is full)
        if self.count == self.average_samples:
            self.sum -= self.buffer[self.index]
        else:
            self.count += 1
        # Add new value
        self.sum += value
        self.buffer[self.index] = value
        # Advance index
        self.index = (self.index + 1) % self.average_samples
        return self.sum / self.count

    # Custom log callback to capture FPS
    def log_callback(self, level, log_str):
        # Convert log_str to string if it's a bytes object
        log_str = log_str.decode() if isinstance(log_str, bytes) else log_str
        # Optional: Print for debugging
        # print(f"Level: {level}, Log: {log_str}")
        # Log message format: "sysmon: 25 FPS (refr_cnt: 8 | redraw_cnt: 1), ..."
        if "sysmon:" in log_str and "FPS" in log_str:
            try:
                # Extract FPS value (e.g., "25" from "sysmon: 25 FPS ...")
                fps_part = log_str.split("FPS")[0].split("sysmon:")[1].strip()
                self.last_fps = int(fps_part)
                self.average_fps = self.moving_average(self.last_fps)
                print(f"Current FPS: {self.last_fps} - Average 10 FPS: {self.average_fps}")
            except (IndexError, ValueError):
                pass
