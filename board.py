import pygame

from piece import Bishop, King, Night, Pawn, Piece, Queen, Rook


class Board:
    LIGHT_TILE = (240, 217, 181)
    DARK_TILE = (181, 136, 99)
    SELECTED_TILE = (246, 246, 105)
    MOVE_HINT = (82, 164, 120)
    CAPTURE_HINT = (196, 71, 71)
    CHECK_HINT = (220, 72, 72)
    SIDEBAR_COLOR = (30, 33, 36)
    PANEL_COLOR = (44, 48, 52)
    TEXT_COLOR = (245, 245, 245)
    SUBTEXT_COLOR = (195, 195, 195)
    WHITE_PIECE = (248, 248, 248)
    BLACK_PIECE = (20, 20, 20)
    START_TIME_SECONDS = 300
    TIME_STEAL_AMOUNT = 15

    def __init__(self, rows, columns, win, board_size=640, sidebar_width=240):
        self.rows = rows
        self.columns = columns
        self.win = win
        self.board_size = board_size
        self.sidebar_width = sidebar_width
        self.tile_size = self.board_size // self.rows
        self.board = [[None for _ in range(self.columns)] for _ in range(self.rows)]
        self.current_turn = "w"
        self.selected_piece = None
        self.valid_moves = []
        self.winner = None
        self.game_state = "White to move"
        self.white_time_left = float(self.START_TIME_SECONDS)
        self.black_time_left = float(self.START_TIME_SECONDS)
        self.cheat_mode = None
        self.cheat_message = "White cheats: X removes a black piece, T steals time."

        pygame.font.init()
        self.piece_font = pygame.font.SysFont("arial", 34, bold=True)
        self.status_font = pygame.font.SysFont("arial", 28, bold=True)
        self.detail_font = pygame.font.SysFont("arial", 22)
        self.small_font = pygame.font.SysFont("arial", 18)

        self._setup_pieces()
        self.update_game_state()

    def _setup_pieces(self):
        back_rank = [Rook, Night, Bishop, Queen, King, Bishop, Night, Rook]
        for column, piece_cls in enumerate(back_rank):
            self.board[0][column] = piece_cls(0, column, "w")
            self.board[7][column] = piece_cls(7, column, "b")

        for column in range(self.columns):
            self.board[1][column] = Pawn(1, column, "w")
            self.board[6][column] = Pawn(6, column, "b")

    def reset(self):
        self.board = [[None for _ in range(self.columns)] for _ in range(self.rows)]
        self.current_turn = "w"
        self.selected_piece = None
        self.valid_moves = []
        self.winner = None
        self.game_state = "White to move"
        self.white_time_left = float(self.START_TIME_SECONDS)
        self.black_time_left = float(self.START_TIME_SECONDS)
        self.cheat_mode = None
        self.cheat_message = "White cheats: X removes a black piece, T steals time."
        self._setup_pieces()
        self.update_game_state()

    def in_bounds(self, row, col):
        return 0 <= row < self.rows and 0 <= col < self.columns

    def get_piece(self, row, col):
        return self.board[row][col]

    def clone(self):
        cloned = Board.__new__(Board)
        cloned.rows = self.rows
        cloned.columns = self.columns
        cloned.win = None
        cloned.board_size = self.board_size
        cloned.sidebar_width = self.sidebar_width
        cloned.tile_size = self.tile_size
        cloned.board = [[None for _ in range(self.columns)] for _ in range(self.rows)]
        cloned.current_turn = self.current_turn
        cloned.selected_piece = None
        cloned.valid_moves = []
        cloned.winner = self.winner
        cloned.game_state = self.game_state
        cloned.white_time_left = self.white_time_left
        cloned.black_time_left = self.black_time_left
        cloned.cheat_mode = self.cheat_mode
        cloned.cheat_message = self.cheat_message
        cloned.piece_font = None
        cloned.status_font = None
        cloned.detail_font = None
        cloned.small_font = None

        for row in range(self.rows):
            for col in range(self.columns):
                piece = self.board[row][col]
                if piece is not None:
                    cloned.board[row][col] = piece.clone()

        return cloned

    def screen_to_board(self, x_pos, y_pos):
        if x_pos < 0 or y_pos < 0 or x_pos >= self.board_size or y_pos >= self.board_size:
            return (None, None)
        column = x_pos // self.tile_size
        row = self.rows - 1 - (y_pos // self.tile_size)
        return (row, column)

    def board_to_screen(self, row, col):
        x_pos = col * self.tile_size
        y_pos = (self.rows - 1 - row) * self.tile_size
        return (x_pos, y_pos)

    def clear_selection(self):
        if self.selected_piece is not None:
            self.selected_piece.deselect_piece()
        self.selected_piece = None
        self.valid_moves = []

    def update(self, delta_seconds):
        if self.winner is not None:
            return

        if self.current_turn == "w":
            self.white_time_left = max(0.0, self.white_time_left - delta_seconds)
            if self.white_time_left <= 0:
                self.winner = "b"
                self.game_state = "White flagged. Black wins on time."
        else:
            self.black_time_left = max(0.0, self.black_time_left - delta_seconds)
            if self.black_time_left <= 0:
                self.winner = "w"
                self.game_state = "Black flagged. White wins on time."

    def click_square(self, row, col):
        if self.winner is not None:
            return

        if self.cheat_mode == "remove_black_piece":
            self._apply_remove_piece_cheat(row, col)
            return

        piece = self.get_piece(row, col)
        if self.selected_piece is None:
            if piece is not None and piece.color == self.current_turn:
                self._select_piece(piece)
            return

        if piece is not None and piece.color == self.current_turn:
            self._select_piece(piece)
            return

        if (row, col) in self.valid_moves:
            self.move_piece(self.selected_piece, row, col)
            return

        self.clear_selection()

    def _select_piece(self, piece):
        self.clear_selection()
        self.selected_piece = piece
        piece.select_piece()
        self.valid_moves = self.get_legal_moves(piece)

    def activate_remove_piece_cheat(self):
        if self.winner is not None:
            return
        self.clear_selection()
        self.cheat_mode = "remove_black_piece"
        self.cheat_message = "Cheat armed: click any black piece to remove it."

    def steal_time_from_black(self):
        if self.winner is not None:
            return
        old_time = self.black_time_left
        self.black_time_left = max(0.0, self.black_time_left - self.TIME_STEAL_AMOUNT)
        self.cheat_mode = None
        removed_seconds = int(round(old_time - self.black_time_left))
        self.cheat_message = f"White cheated: Black lost {removed_seconds} seconds."
        if self.black_time_left <= 0:
            self.winner = "w"
            self.game_state = "Black flagged. White wins on time."
        else:
            self.update_game_state()

    def _apply_remove_piece_cheat(self, row, col):
        piece = self.get_piece(row, col)
        self.cheat_mode = None
        if piece is None or piece.color != "b":
            self.cheat_message = "Cheat cancelled: click a black piece next time."
            return

        self.board[row][col] = None
        self.clear_selection()
        if isinstance(piece, King):
            self.winner = "w"
            self.game_state = "White deleted the black king."
            self.cheat_message = "White cheat used: the black king was removed."
            return

        self.cheat_message = f"White cheat used: removed Black's {piece.__class__.__name__}."
        self.update_game_state()

    def move_piece(self, piece, row, col):
        origin_row, origin_col = piece.get_position()
        self.board[origin_row][origin_col] = None
        piece.update_position(row, col)
        self.board[row][col] = piece

        if isinstance(piece, Pawn) and row in (0, self.rows - 1):
            self.board[row][col] = Queen(row, col, piece.color)

        self.current_turn = "b" if self.current_turn == "w" else "w"
        self.clear_selection()
        self.update_game_state()

    def get_legal_moves(self, piece):
        legal_moves = []
        for row, col in piece.get_candidate_moves(self):
            trial_board = self.clone()
            trial_piece = trial_board.get_piece(piece.row_number, piece.column_number)
            trial_board._move_piece_no_validation(trial_piece, row, col)
            if not trial_board.is_in_check(piece.color):
                legal_moves.append((row, col))
        return legal_moves

    def _move_piece_no_validation(self, piece, row, col):
        origin_row, origin_col = piece.get_position()
        self.board[origin_row][origin_col] = None
        piece.update_position(row, col)
        self.board[row][col] = piece
        if isinstance(piece, Pawn) and row in (0, self.rows - 1):
            self.board[row][col] = Queen(row, col, piece.color)

    def _find_king(self, color):
        for row in self.board:
            for piece in row:
                if isinstance(piece, King) and piece.color == color:
                    return piece
        return None

    def is_in_check(self, color):
        king = self._find_king(color)
        if king is None:
            return False
        king_row, king_col = king.get_position()
        for row in self.board:
            for piece in row:
                if piece is not None and piece.color != color and piece.attacks_square(self, king_row, king_col):
                    return True
        return False

    def player_has_moves(self, color):
        for row in self.board:
            for piece in row:
                if piece is not None and piece.color == color and self.get_legal_moves(piece):
                    return True
        return False

    def update_game_state(self):
        if self.winner in ("w", "b", "draw"):
            return

        white_king = self._find_king("w")
        black_king = self._find_king("b")
        if white_king is None:
            self.winner = "b"
            self.game_state = "White king is gone. Black wins."
            return
        if black_king is None:
            self.winner = "w"
            self.game_state = "Black king is gone. White wins."
            return

        side_name = "White" if self.current_turn == "w" else "Black"
        in_check = self.is_in_check(self.current_turn)
        has_moves = self.player_has_moves(self.current_turn)

        if not has_moves:
            if in_check:
                self.winner = "b" if self.current_turn == "w" else "w"
                winner_name = "White" if self.winner == "w" else "Black"
                self.game_state = f"Checkmate! {winner_name} wins."
            else:
                self.winner = "draw"
                self.game_state = "Stalemate. Draw."
            return

        self.winner = None
        if in_check:
            self.game_state = f"{side_name} is in check"
        else:
            self.game_state = f"{side_name} to move"

    def draw(self):
        self._draw_board()
        self._draw_pieces()
        self._draw_sidebar()

    def _draw_board(self):
        for row in range(self.rows):
            for col in range(self.columns):
                x_pos, y_pos = self.board_to_screen(row, col)
                tile_color = self.LIGHT_TILE if (row + col) % 2 == 0 else self.DARK_TILE
                if self.selected_piece is not None and self.selected_piece.get_position() == (row, col):
                    tile_color = self.SELECTED_TILE
                pygame.draw.rect(
                    self.win,
                    tile_color,
                    (x_pos, y_pos, self.tile_size, self.tile_size),
                )

                if (row, col) in self.valid_moves:
                    target = self.get_piece(row, col)
                    hint_color = self.CAPTURE_HINT if target is not None else self.MOVE_HINT
                    center = (x_pos + self.tile_size // 2, y_pos + self.tile_size // 2)
                    radius = 12 if target is None else (self.tile_size // 2) - 10
                    width = 0 if target is None else 5
                    pygame.draw.circle(self.win, hint_color, center, radius, width)

        checked_king = self._find_king(self.current_turn) if self.is_in_check(self.current_turn) else None
        if checked_king is not None:
            x_pos, y_pos = self.board_to_screen(*checked_king.get_position())
            pygame.draw.rect(
                self.win,
                self.CHECK_HINT,
                (x_pos + 4, y_pos + 4, self.tile_size - 8, self.tile_size - 8),
                border_radius=10,
            )

    def _draw_pieces(self):
        for row in self.board:
            for piece in row:
                if piece is None:
                    continue
                board_row, board_col = piece.get_position()
                x_pos, y_pos = self.board_to_screen(board_row, board_col)
                center = (x_pos + self.tile_size // 2, y_pos + self.tile_size // 2)
                outer_color = (55, 55, 55) if piece.color == "w" else (210, 210, 210)
                inner_color = self.WHITE_PIECE if piece.color == "w" else self.BLACK_PIECE
                text_color = (25, 25, 25) if piece.color == "w" else (245, 245, 245)

                pygame.draw.circle(self.win, outer_color, center, (self.tile_size // 2) - 10)
                pygame.draw.circle(self.win, inner_color, center, (self.tile_size // 2) - 14)

                text_surface = self.piece_font.render(piece.label, True, text_color)
                text_rect = text_surface.get_rect(center=(center[0], center[1] + 1))
                self.win.blit(text_surface, text_rect)

    def _draw_sidebar(self):
        sidebar_x = self.board_size
        sidebar_height = self.win.get_height() if self.win is not None else self.board_size
        pygame.draw.rect(
            self.win,
            self.SIDEBAR_COLOR,
            (sidebar_x, 0, self.sidebar_width, sidebar_height),
        )

        y_pos = 20
        y_pos = self._draw_panel(
            sidebar_x + 14,
            y_pos,
            self.sidebar_width - 28,
            "Simple Chess",
            [self.game_state],
            title_font=self.status_font,
            body_font=self.detail_font,
            body_color=self.TEXT_COLOR,
        )
        y_pos = self._draw_panel(
            sidebar_x + 14,
            y_pos,
            self.sidebar_width - 28,
            "Game",
            [
                f"Turn: {'White' if self.current_turn == 'w' else 'Black'}",
                f"White clock: {self._format_time(self.white_time_left)}",
                f"Black clock: {self._format_time(self.black_time_left)}",
            ],
        )
        y_pos = self._draw_panel(
            sidebar_x + 14,
            y_pos,
            self.sidebar_width - 28,
            "Controls",
            [
                "Click a piece, then click a highlighted square.",
                "Press R to restart the match.",
                "Press X to remove a black piece on your next click.",
                "Press T to steal 15 seconds from Black.",
            ],
        )
        y_pos = self._draw_panel(
            sidebar_x + 14,
            y_pos,
            self.sidebar_width - 28,
            "Cheat Status",
            [self.cheat_message],
        )
        self._draw_captured_summary(sidebar_x + 14, y_pos, self.sidebar_width - 28)

    def _draw_captured_summary(self, panel_x, start_y, panel_width):
        white_count = 0
        black_count = 0
        for row in self.board:
            for piece in row:
                if piece is None:
                    continue
                if piece.color == "w":
                    white_count += 1
                else:
                    black_count += 1

        white_captured = 16 - white_count
        black_captured = 16 - black_count
        labels = [
            f"White lost: {white_captured}",
            f"Black lost: {black_captured}",
        ]
        self._draw_panel(panel_x, start_y, panel_width, "Captured", labels)

    def _format_time(self, seconds_left):
        total_seconds = max(0, int(seconds_left))
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02}:{seconds:02}"

    def _draw_wrapped_lines(self, lines, font, color, x_pos, start_y, line_spacing, max_width):
        y_pos = start_y
        for line in lines:
            words = line.split()
            current_line = ""
            for word in words:
                candidate = word if not current_line else f"{current_line} {word}"
                if font.size(candidate)[0] <= max_width:
                    current_line = candidate
                else:
                    rendered = font.render(current_line, True, color)
                    self.win.blit(rendered, (x_pos, y_pos))
                    y_pos += rendered.get_height() + line_spacing
                    current_line = word
            if current_line:
                rendered = font.render(current_line, True, color)
                self.win.blit(rendered, (x_pos, y_pos))
                y_pos += rendered.get_height() + line_spacing
        return y_pos

    def _draw_panel(
        self,
        x_pos,
        y_pos,
        width,
        title,
        body_lines,
        title_font=None,
        body_font=None,
        body_color=None,
    ):
        title_font = title_font or self.detail_font
        body_font = body_font or self.small_font
        body_color = body_color or self.SUBTEXT_COLOR
        panel_padding = 14
        title_surface = title_font.render(title, True, self.TEXT_COLOR)
        body_start_y = y_pos + panel_padding + title_surface.get_height() + 10
        body_end_y = self._draw_wrapped_lines(
            body_lines,
            body_font,
            body_color,
            x_pos + panel_padding,
            body_start_y,
            8,
            width - (panel_padding * 2),
        )
        panel_height = max(60, body_end_y - y_pos + panel_padding - 8)
        pygame.draw.rect(
            self.win,
            self.PANEL_COLOR,
            (x_pos, y_pos, width, panel_height),
            border_radius=12,
        )
        pygame.draw.rect(
            self.win,
            (70, 74, 79),
            (x_pos, y_pos, width, panel_height),
            1,
            border_radius=12,
        )
        self.win.blit(title_surface, (x_pos + panel_padding, y_pos + panel_padding))
        self._draw_wrapped_lines(
            body_lines,
            body_font,
            body_color,
            x_pos + panel_padding,
            body_start_y,
            8,
            width - (panel_padding * 2),
        )
        return y_pos + panel_height + 14
