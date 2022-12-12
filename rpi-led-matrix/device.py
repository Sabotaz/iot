#!/usr/bin/env python
# -*- coding: utf-8 -*-

import spidev
import time
import font


class Constants:
    MAX7219_REG_NOOP = 0x0
    MAX7219_REG_DIGIT0 = 0x1
    MAX7219_REG_DIGIT1 = 0x2
    MAX7219_REG_DIGIT2 = 0x3
    MAX7219_REG_DIGIT3 = 0x4
    MAX7219_REG_DIGIT4 = 0x5
    MAX7219_REG_DIGIT5 = 0x6
    MAX7219_REG_DIGIT6 = 0x7
    MAX7219_REG_DIGIT7 = 0x8
    MAX7219_REG_DECODEMODE = 0x9
    MAX7219_REG_INTENSITY = 0xA
    MAX7219_REG_SCANLIMIT = 0xB
    MAX7219_REG_SHUTDOWN = 0xC
    MAX7219_REG_DISPLAYTEST = 0xF


class Device:
    """
    Base class for handling multiple cascaded MAX7219 devices.
    Callers should generally pick either the sevensegment or matrix
    subclasses instead depending on which application is required.
    A buffer is maintained which holds the bytes that will be cascaded
    every time flush() is called.
    """
    NUM_DIGITS = 8

    def __init__(self, cascaded=1, spi_bus=0, spi_device=0):
        """
        Constructor: cascaded should be the number of cascaded MAX7219
        devices are connected.
        """
        assert cascaded > 0, "Must have at least one device!"

        self._cascaded = cascaded
        self._buffer = [0] * self.NUM_DIGITS * self._cascaded
        self._spi = spidev.SpiDev()
        self._spi.open(spi_bus, spi_device)

        self.command(Constants.MAX7219_REG_SCANLIMIT, 7)    # show all 8 digits
        self.command(Constants.MAX7219_REG_DECODEMODE, 0)   # use matrix (not digits)
        self.command(Constants.MAX7219_REG_DISPLAYTEST, 0)  # no display test
        self.command(Constants.MAX7219_REG_SHUTDOWN, 1)     # not shutdown mode
        self.brightness(7)                                  # intensity: range: 0..15
        self.clear()

    def command(self, register, data):
        assert Constants.MAX7219_REG_DECODEMODE <= register <= Constants.MAX7219_REG_DISPLAYTEST
        self._write([register, data] * self._cascaded)

    def _write(self, data):
        """
        Send the bytes (which should comprise of alternating command,
        data values) over the SPI device.
        """
        self._spi.xfer2(list(data))

    def _values(self, position):
        """
        A generator which yields the digit/column position and the data
        value from that position for each of the cascaded devices.
        """
        for deviceId in range(self._cascaded):
            yield position + Constants.MAX7219_REG_DIGIT0
            yield self._buffer[(deviceId * self.NUM_DIGITS) + position]

    def clear(self, deviceId=None):
        """
        Clears the buffer the given deviceId if specified (else clears all
        devices), and flushes.
        """
        assert not deviceId or 0 <= deviceId < self._cascaded, "Invalid deviceId: {0}".format(deviceId)

        if deviceId is None:
            start = 0
            end = self._cascaded
        else:
            start = deviceId
            end = deviceId + 1

        for deviceId in range(start, end):
            for position in range(self.NUM_DIGITS):
                self.set_byte(deviceId,
                              position + Constants.MAX7219_REG_DIGIT0,
                              0, redraw=False)

        self.flush()

    def flush(self):
        """
        For each digit/column, cascade out the contents of the buffer
        cells to the SPI device.
        """
        for posn in range(self.NUM_DIGITS):
            self._write(self._values(posn))

    def brightness(self, intensity):
        """
        Sets the brightness level of all cascaded devices to the same
        intensity level, ranging from 0..16
        """
        assert 0 <= intensity < 16, "Invalid brightness: {0}".format(intensity)
        self.command(Constants.MAX7219_REG_INTENSITY, intensity)

    def set_byte(self, deviceId, position, value, redraw=True):
        """
        Low level mechanism to set a byte value in the buffer array. If redraw
        is not suppled, or set to True, will force a redraw of _all_ buffer
        items: If you are calling this method rapidly/frequently (e.g in a
        loop), it would be more efficient to set to False, and when done,
        call flush().
        Prefer to use the higher-level method calls in the subclasses below.
        """
        assert 0 <= deviceId < self._cascaded, "Invalid deviceId: {0}".format(deviceId)
        assert Constants.MAX7219_REG_DIGIT0 <= position <= Constants.MAX7219_REG_DIGIT7, "Invalid digit/column: {0}".format(position)

        offset = (deviceId * self.NUM_DIGITS) + position - Constants.MAX7219_REG_DIGIT0
        self._buffer[offset] = value

        if redraw:
            self.flush()

    def scroll_left(self, redraw=True):

        del self._buffer[0]
        self._buffer.append(0)
        if redraw:
            self.flush()

    def scroll_right(self, redraw=True):

        del self._buffer[self.NUM_DIGITS - 1]
        self._buffer.insert(0, 0)
        if redraw:
            self.flush()


class Matrix(Device):
    """
    Implementation of MAX7219 devices cascaded with a series of 8x8 LED
    matrix devices. It provides a convenient methods to write letters
    to specific devices, to scroll a large message from left-to-right, or
    to set specific pixels. It is assumed the matrices are linearly aligned.
    """

    def letter(self, deviceId, asciiCode, font=font.CP437_FONT, redraw=True):
        """
        Writes the ASCII letter code to the given device in the specified font.
        """
        assert 0 <= asciiCode < 256
        col = Constants.MAX7219_REG_DIGIT0
        for value in font[asciiCode]:
            if col > Constants.MAX7219_REG_DIGIT7:
                self.clear(deviceId)
                raise OverflowError('Font for \'{0}\' too large for display'.format(asciiCode))

            self.set_byte(deviceId, col, value, redraw=False)
            col += 1

        if redraw:
            self.flush()

    def scroll_up(self, redraw=True):
        """
        Scrolls the underlying buffer (for all cascaded devices) up one pixel
        """
        self._buffer = [value >> 1 for value in self._buffer]
        if redraw:
            self.flush()

    def scroll_down(self, redraw=True):
        """
        Scrolls the underlying buffer (for all cascaded devices) down one pixel
        """
        self._buffer = [value << 1 for value in self._buffer]
        if redraw:
            self.flush()

    def show_message(self, text, font=font.CP437_FONT, delay=0.05):
        """
        Transitions the text message across the devices from left-to-right
        """
        # Add some spaces on (same number as cascaded devices) so that the
        # message scrolls off to the left completely.
        text += ' ' * self._cascaded
        src = (value for asciiCode in text for value in font[ord(asciiCode)])

        for value in src:
            time.sleep(delay)
            self.scroll_left(redraw=False)
            self._buffer[-1] = value
            self.flush()

    def str(self, text, font=font.CP437_FONT):
        """
        Print a string to the display, cutting off if too long
        """
        src = (value for asciiCode in text for value in font[ord(asciiCode)])
        # remove any repeated zeros
        s2 = []
        for val in src:
            if (val != 0 or s2[-1] != 0):
                s2.append(val)
        n0 = len(self._buffer)
        n1 = len(s2)
        if (n0 > n1):
            s2.extend([0]*(n0 - n1))
        _buffer = s2[:n0]
        self.flush()

    def pixel(self, x, y, value, redraw=True):
        """
        Sets (value = 1) or clears (value = 0) the pixel at the given
        co-ordinate. It may be more efficient to batch multiple pixel
        operations together with redraw=False, and then call flush()
        to redraw just once.
        """
        assert 0 <= x < len(self._buffer)
        assert 0 <= y < 8

        if value:
            self._buffer[y] |= (1 << x)
        else:
            self._buffer[y] &= ~(1 << x)

        if redraw:
            self.flush()
