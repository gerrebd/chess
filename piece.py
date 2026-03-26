class Piece:
    symbol_map = {}
    label_map = {}

    def __init__(self, row_number, column_number, color):
        self.row_number = row_number
        self.column_number = column_number
        self.color = color
        self.selected = False

    def get_position(self):
        return (self.row_number, self.column_number)

    def update_position(self, row_number, column_number):
        self.row_number = row_number
        self.column_number = column_number
        return self.get_position()

    def get_color(self):
        return self.color

    def select_piece(self):
        self.selected = True

    def deselect_piece(self):
        self.selected = False

    def clone(self):
        return type(self)(self.row_number, self.column_number, self.color)

    @property
    def symbol(self):
        return self.symbol_map[self.color]

    @property
    def label(self):
        return self.label_map[self.color]

    def attacks_square(self, board, row, col):
        return (row, col) in self.get_candidate_moves(board)

    def get_candidate_moves(self, board):
        raise NotImplementedError

    def _sliding_moves(self, board, directions):
        moves = []
        for row_step, col_step in directions:
            row = self.row_number + row_step
            col = self.column_number + col_step
            while board.in_bounds(row, col):
                target = board.get_piece(row, col)
                if target is None:
                    moves.append((row, col))
                else:
                    if target.color != self.color:
                        moves.append((row, col))
                    break
                row += row_step
                col += col_step
        return moves


class Pawn(Piece):
    symbol_map = {"w": "♙", "b": "♟"}
    label_map = {"w": "P", "b": "P"}

    def get_candidate_moves(self, board):
        moves = []
        direction = 1 if self.color == "w" else -1
        start_row = 1 if self.color == "w" else 6
        one_step_row = self.row_number + direction

        if board.in_bounds(one_step_row, self.column_number) and board.get_piece(one_step_row, self.column_number) is None:
            moves.append((one_step_row, self.column_number))
            two_step_row = self.row_number + (2 * direction)
            if self.row_number == start_row and board.get_piece(two_step_row, self.column_number) is None:
                moves.append((two_step_row, self.column_number))

        for delta_col in (-1, 1):
            next_row = self.row_number + direction
            next_col = self.column_number + delta_col
            if not board.in_bounds(next_row, next_col):
                continue
            target = board.get_piece(next_row, next_col)
            if target is not None and target.color != self.color:
                moves.append((next_row, next_col))

        return moves

    def attacks_square(self, board, row, col):
        direction = 1 if self.color == "w" else -1
        return row == self.row_number + direction and col in (self.column_number - 1, self.column_number + 1)


class Night(Piece):
    symbol_map = {"w": "♘", "b": "♞"}
    label_map = {"w": "N", "b": "N"}

    def get_candidate_moves(self, board):
        moves = []
        offsets = (
            (-2, -1),
            (-2, 1),
            (-1, -2),
            (-1, 2),
            (1, -2),
            (1, 2),
            (2, -1),
            (2, 1),
        )
        for row_step, col_step in offsets:
            row = self.row_number + row_step
            col = self.column_number + col_step
            if not board.in_bounds(row, col):
                continue
            target = board.get_piece(row, col)
            if target is None or target.color != self.color:
                moves.append((row, col))
        return moves


class Bishop(Piece):
    symbol_map = {"w": "♗", "b": "♝"}
    label_map = {"w": "B", "b": "B"}

    def get_candidate_moves(self, board):
        return self._sliding_moves(board, ((1, 1), (1, -1), (-1, 1), (-1, -1)))


class Rook(Piece):
    symbol_map = {"w": "♖", "b": "♜"}
    label_map = {"w": "R", "b": "R"}

    def get_candidate_moves(self, board):
        return self._sliding_moves(board, ((1, 0), (-1, 0), (0, 1), (0, -1)))


class King(Piece):
    symbol_map = {"w": "♔", "b": "♚"}
    label_map = {"w": "K", "b": "K"}

    def get_candidate_moves(self, board):
        moves = []
        for row_step in (-1, 0, 1):
            for col_step in (-1, 0, 1):
                if row_step == 0 and col_step == 0:
                    continue
                row = self.row_number + row_step
                col = self.column_number + col_step
                if not board.in_bounds(row, col):
                    continue
                target = board.get_piece(row, col)
                if target is None or target.color != self.color:
                    moves.append((row, col))
        return moves


class Queen(Piece):
    symbol_map = {"w": "♕", "b": "♛"}
    label_map = {"w": "Q", "b": "Q"}

    def get_candidate_moves(self, board):
        return self._sliding_moves(
            board,
            ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)),
        )
