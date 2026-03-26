import pygame

from board import Board


BOARD_SIZE = 640
SIDEBAR_WIDTH = 320
WINDOW_WIDTH = BOARD_SIZE + SIDEBAR_WIDTH
WINDOW_HEIGHT = 760
BACKGROUND = (18, 18, 18)


def redraw_game_window(win, board):
    win.fill(BACKGROUND)
    board.draw()
    pygame.display.flip()


def main():
    pygame.init()
    pygame.display.set_caption("Simple Chess")
    win = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    board = Board(8, 8, win, board_size=BOARD_SIZE, sidebar_width=SIDEBAR_WIDTH)
    clock = pygame.time.Clock()
    running = True

    while running:
        delta_seconds = clock.tick(60) / 1000
        board.update(delta_seconds)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    board.reset()
                elif event.key == pygame.K_x:
                    board.activate_remove_piece_cheat()
                elif event.key == pygame.K_t:
                    board.steal_time_from_black()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                row, col = board.screen_to_board(*event.pos)
                if row is not None:
                    board.click_square(row, col)
                else:
                    board.clear_selection()

        redraw_game_window(win, board)

    pygame.quit()


if __name__ == "__main__":
    main()
