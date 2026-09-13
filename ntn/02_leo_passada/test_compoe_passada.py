import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))

import compoe_passada  # noqa: E402
import plot_snr  # noqa: E402


class ComposicaoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cab, saida, (nascer, pico, por) = compoe_passada.compor()
        cls.cab, cls.saida = cab, saida
        cls.nascer, cls.pico, cls.por = nascer, pico, por
        cls.tmp = tempfile.mkdtemp()
        cls.path = os.path.join(cls.tmp, "passada_sintetica_SIOT1.txt")
        compoe_passada.escrever(cls.path, cab, saida)
        (cls.utc_fix, cls.dev_fix_td, _anchors, _fb, _fbd, cls.records, cls.events,
         cls.lat, cls.lon, _ul, _dl, _sib, _cfun, cls.no_cell, _idle, _rel,
         cls.t310, cls.cereg) = plot_snr.load_log(cls.path)

    def test_passada_de_referencia(self):
        self.assertEqual(self.nascer.strftime("%H:%M"), "02:22")
        self.assertEqual(self.pico.strftime("%H:%M"), "02:28")
        self.assertEqual(self.por.strftime("%H:%M"), "02:35")

    def test_cabecalho_declara_origem_e_marca(self):
        self.assertTrue(self.cab.startswith("# sintetico"))
        for nome in ["20260907_0228_SIOT1_BRA_KY.txt", "20260909_0233_SIOT1_BRA_KY.txt",
                     "20260412_1349_SIOT3_BRA.txt"]:
            self.assertIn(nome, self.cab)
        self.assertIn("[sintetico]", self.cab)

    def test_linhas_geradas_marcadas_e_so_na_busca(self):
        geradas = [d for d, t, o in self.saida if o == "gerado"]
        self.assertTrue(geradas)
        self.assertTrue(all("[sintetico]" in t for _, t, o in self.saida if o == "gerado"))
        self.assertGreater(min(geradas), self.nascer)
        self.assertLess(max(geradas), self.pico)

    def test_plot_snr_le_e_encontra_a_sequencia(self):
        self.assertEqual((self.lat, self.lon), (compoe_passada.LAT, compoe_passada.LON))
        # ordem real do trace de 07/09: o Attach Request e montado antes do Msg3 (RAR),
        # e o +CSCON: 1 chega antes do Attach Accept
        ordem = ["MIB", "SIB1", "SIBx", "Attach Req", "RAR", "CSCON=1", "Attach Accept",
                 "UDP Send", "UDP Recv"]
        primeiros = []
        for label in ordem:
            self.assertTrue(self.events[label], f"sem evento {label}")
            primeiros.append(min(self.events[label]))
        self.assertEqual(primeiros, sorted(primeiros))
        self.assertTrue(self.t310, "sem T310")
        self.assertGreater(min(self.t310), max(self.events["UDP Recv"]))
        # NO_CELL antes do MIB (busca) e depois do T310 (perda da celula); nunca no meio
        mib, t310 = min(self.events["MIB"]), min(self.t310)
        busca = [td for td in self.no_cell if td < mib]
        self.assertTrue(busca, "sem ciclo de busca antes do MIB")
        self.assertFalse([td for td in self.no_cell if mib <= td < t310])
        self.assertTrue(self.events["CSCON=0"])
        self.assertTrue(self.records, "sem medidas de RSRP")

    def test_t310_na_descida_e_attach_na_subida(self):
        def utc(td):
            return plot_snr.dev_to_utc(td, self.utc_fix, self.dev_fix_td)
        pico = self.pico.replace(tzinfo=None)
        self.assertLess(utc(min(self.events["MIB"])), pico)
        self.assertGreater(utc(min(self.t310)), pico)
        self.assertLess(utc(min(self.t310)), self.por.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
