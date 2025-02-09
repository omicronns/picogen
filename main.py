from machine import Pin, mem32, freq as cpu_freq
from rp2 import PIO, StateMachine, asm_pio, DMA
from uctypes import addressof
from array import array
from math import sin, pi, log2
import time

DMA_BASE = 0x50000000
CH0_READ_ADDR = DMA_BASE+0x000

samp_per_word = 4

cpu_freq(300_000_000)

@asm_pio(out_init=(PIO.OUT_LOW,) * 8,
         out_shiftdir=PIO.SHIFT_RIGHT,
         autopull=True,
         pull_thresh=8 * samp_per_word,
         fifo_join=PIO.JOIN_TX)
def stream():
    out(pins, 8)

class Generator:
    SIN_FN = lambda n, period: (sin(2*pi*n/period) + 1)/2
    SQR_FN = lambda n, period: 1 if n * 2 > period else 0
    SAW_FN = lambda n, period: (n % period) / period

    def __init__(self):
        self.dma0=DMA()
        self.dma1=DMA()
        self.ctl0 = self.dma0.pack_ctrl(inc_write=False, treq_sel=0x00, chain_to=1)
        self.ctl1 = self.dma1.pack_ctrl(inc_read=False, inc_write=False, treq_sel=0x3f, chain_to=0)
        self.sm = None
        self.buf = bytearray(256)
        self.p=array('I',[addressof(self.buf)])
        self.dma1.config(read=self.p, write=CH0_READ_ADDR, count=1, ctrl=self.ctl1)

    def enable(self, state):
        self.dma0.ctrl = 0
        self.dma0.active(0)
        if state:
            self.dma0.ctrl = self.ctl0
            self.dma0.active(1)

    def _wave_gen(self, freq, func):
        if freq * 256 > cpu_freq():
            freq_sm = cpu_freq()
            samples_count = freq_sm // freq
        else:
            samples_count = 256
            freq_sm = samples_count * freq
        buf_len = (samples_count // 4) * 4

        for n in range(buf_len):
            val = int(func(n, samples_count) * 255)
            self.buf[n] = val

        return buf_len, freq_sm

    def run(self, freq, fn):
        buf_len, freq_sm = self._wave_gen(freq, fn)
        print("buffer depth: {}\npio freq: {}".format(buf_len, freq_sm))
        self.sm = StateMachine(0, stream, freq=freq_sm, out_base=Pin(0))
        self.sm.active(1)
        self.dma0.config(read=self.buf, write=self.sm, count=buf_len // 4, ctrl=self.ctl0)
        self.enable(True)

gen = Generator()
