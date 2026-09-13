import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skylo_test  # noqa: E402


class CommandTablesTest(unittest.TestCase):
    def test_config_sequence(self):
        cmds = [c for c, _ in skylo_test.build_config_commands("-3.1", "-60.0", "50", "em")]
        self.assertEqual(cmds[0], "AT%XSYSTEMMODE=0,0,0,0,1")
        self.assertEqual(cmds[1], 'AT%XBANDLOCK=2,,"255,256"')
        self.assertIn('AT%LOCATION=2,"-3.1","-60.0","50",0,0', cmds)
        self.assertIn('AT+CGDCONT=0,"ip","em"', cmds)

    def test_no_mandatory_sib32(self):
        notif = [c for c, _ in skylo_test.NOTIFICATION_COMMANDS]
        post = [c for c, _ in skylo_test.POST_REGISTRATION_COMMANDS]
        self.assertNotIn("AT%SIBCONFIG=32,0", notif + post)
        # %SIBREQ responde +CME ERROR 517 com o modem desligado: so depois do registro
        self.assertNotIn("AT%SIBREQ=32", notif)
        self.assertIn("AT%SIBREQ=32", post)

    def test_send_uses_handle_and_notify_flag(self):
        self.assertEqual(skylo_test.send_payload_cmd(1, "ola", notify=True),
                         'AT#XSEND=1,0,8192,"ola"')
        self.assertEqual(skylo_test.send_payload_cmd(1, "ola", notify=False),
                         'AT#XSEND=1,0,0,"ola"')

    def test_post_registration_reads_band_and_channel(self):
        cmds = [c for c, _ in skylo_test.POST_REGISTRATION_COMMANDS]
        self.assertIn("AT+COPS?", cmds)
        self.assertIn("AT%XMONITOR", cmds)

    def test_no_default_coordinates(self):
        self.assertFalse(hasattr(skylo_test, "DEFAULT_LAT"))


if __name__ == "__main__":
    unittest.main()
