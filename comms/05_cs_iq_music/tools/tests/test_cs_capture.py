# -*- coding: utf-8 -*-
import cs_capture


LINES = [
    "*** Booting nRF Connect SDK v3.4.0 ***\n",
    "IQ,1,0,2,1.0,2.0,3.0,4.0\n",
    "lixo\n",
    "CS,1,0,1,3.000,3.000,2.998,1,40\n",
]


def test_filter_lines_keeps_only_valid():
    assert list(cs_capture.filter_lines(LINES)) == [LINES[1], LINES[3]]


def test_looks_like_ours():
    assert cs_capture.looks_like_ours(LINES)
    assert not cs_capture.looks_like_ours(["87799 67,9602,535,1,-3,0\n"] * 10)   # CSV do lab 03 do Edge AI
    assert not cs_capture.looks_like_ours([])


def test_waiting_for_tag():
    prompt = "\nEndereco BLE do tag (ex.: EC:EF:40:2D:5E:46 random): "
    assert cs_capture.waiting_for_tag([prompt])
    assert cs_capture.waiting_for_tag(["lixo\n", prompt, "IQ,1,0,2,1,2,3,4\n"])
    assert not cs_capture.waiting_for_tag(LINES)
    assert not cs_capture.waiting_for_tag([])


def test_responder_tag():
    import cs_csv

    class Porta:
        def __init__(self):
            self.dados = b""

        def write(self, b):
            self.dados += b

        def flush(self):
            pass

    p = Porta()
    cs_csv.responder_tag(p, None)
    assert p.dados == b""
    cs_csv.responder_tag(p, " EC:EF:40:2D:5E:46 ")
    assert p.dados == b"EC:EF:40:2D:5E:46\r\n"
