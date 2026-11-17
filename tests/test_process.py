import copy
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("codec_process", ROOT / "process.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.config = copy.deepcopy(p.CODECS)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(lambda: setattr(p, "CODECS", self.config))
        self.root = Path(self.tmp.name)
        self.source = self.root / "Sprache mit Leerzeichen.wav"
        p.ffmpeg("ffmpeg", ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=0.317",
                             "-ac", "2", str(self.source)])

    def test_all_codecs_format_names_duration_signal(self):
        profiles = p.build_profiles()
        p.check_encoders("ffmpeg", profiles)
        output = self.root / "Output"
        p.process_audio("ffmpeg", self.source, output, profiles)
        self.assertEqual({f.name for f in output.iterdir()}, {
            "Sprache mit Leerzeichen_opus_32kbps.wav",
            "Sprache mit Leerzeichen_amr_wb_12.65kbps_dtx_on.wav",
            "Sprache mit Leerzeichen_g711_mulaw_64kbps.wav"})
        frames = len(p.decode_to_pcm("ffmpeg", self.source)) // 3
        for path in output.iterdir():
            with wave.open(str(path)) as audio:
                self.assertEqual((audio.getnchannels(), audio.getframerate(), audio.getsampwidth(), audio.getnframes()),
                                 (1, 48000, 3, frames))
                self.assertTrue(any(audio.readframes(frames)))

    def test_dtx_reduces_silence_frames(self):
        silent = self.root / "silent.wav"
        p.ffmpeg("ffmpeg", ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "2", str(silent)])
        sizes = []
        for enabled in (False, True):
            config = dict(p.CODECS["amr_wb"], dtx=enabled)
            encoded = self.root / f"{enabled}.amr"
            p.encode_amr("ffmpeg", silent, encoded, config)
            sizes.append(encoded.stat().st_size)
            self.assertTrue(p.decode_to_pcm("ffmpeg", encoded))
        self.assertLess(sizes[1], sizes[0])

    def test_invalid_settings(self):
        for codec, key, value in [("opus", "bitrate_bps", 5999), ("opus", "application", "invalid"),
                                   ("opus", "vbr", "invalid"), ("opus", "frame_duration_ms", 7),
                                   ("amr_wb", "dtx", "yes"), ("amr_wb", "bitrate_bps", 12000),
                                   ("g711_mulaw", "sample_rate", 16000)]:
            p.CODECS = copy.deepcopy(self.config)
            p.CODECS[codec][key] = value
            with self.subTest(codec=codec, key=key), self.assertRaises(ValueError):
                p.build_profiles()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "process.py"), *map(str, args)], capture_output=True)

    def test_cli_no_overwrite(self):
        output = self.root / "Output"
        self.assertEqual(self.cli(self.source, "--output", output).returncode, 0)
        before = {f.name: f.read_bytes() for f in output.iterdir()}
        self.assertNotEqual(self.cli(self.source, "--output", output).returncode, 0)
        self.assertEqual(before, {f.name: f.read_bytes() for f in output.iterdir()})

    def test_duplicate_stems_rejected(self):
        other = self.root / "sub" / self.source.name
        other.parent.mkdir()
        other.write_bytes(self.source.read_bytes())
        self.assertNotEqual(self.cli(self.source, other, "--output", self.root / "Output").returncode, 0)
        self.assertFalse((self.root / "Output").exists())

    def test_corrupt_input_no_outputs(self):
        self.source.write_bytes(b"not audio")
        self.assertNotEqual(self.cli(self.source, "--output", self.root / "Output").returncode, 0)
        self.assertFalse((self.root / "Output").exists())

    def test_dtx_off_filename(self):
        output = self.root / "Output"
        self.assertEqual(self.cli(self.source, "--amr-dtx", "off", "--output", output).returncode, 0)
        self.assertTrue((output / "Sprache mit Leerzeichen_amr_wb_12.65kbps_dtx_off.wav").exists())


if __name__ == "__main__":
    unittest.main()
