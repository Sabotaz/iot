import time
from random import randrange
import device

matrix = device.Matrix(cascaded=4)
matrix.show_message("Hello world!")

for x in range(256):
    # matrix.letter(1, 32 + (x % 64))
    matrix.letter(0, x)
    time.sleep(0.1)

while True:
    for x in range(500):
        matrix.pixel(4, 4, 1, redraw=False)
        direction = randrange(8)
        if direction == 7 or direction == 0 or direction == 1:
            matrix.scroll_up(redraw=False)
        if direction == 1 or direction == 2 or direction == 3:
            matrix.scroll_right(redraw=False)
        if direction == 3 or direction == 4 or direction == 5:
            matrix.scroll_down(redraw=False)
        if direction == 5 or direction == 6 or direction == 7:
            matrix.scroll_left(redraw=False)

        matrix.flush()
        time.sleep(0.01)
