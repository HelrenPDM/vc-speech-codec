import argparse
import ctypes
import ctypes.util
import os
import sys
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path


# ==================================================
# KONFIGURATION
# ==================================================

# Pfad zu deinem selbst gebauten FFmpeg.
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")

# Alternative: FFmpeg aus dem PATH verwenden.
# FFMPEG = "ffmpeg"

# Alle Ergebnisse direkt in diesem Ordner speichern.
# Relativ zum Arbeitsverzeichnis beim Start des Skripts.
OUTPUT = Path("Output")

# Einheitliches Ausgabeformat für ALLE Dateien.
OUTPUT_RATE = 48000
OUTPUT_CHANNELS = 1
OUTPUT_SAMPLE_WIDTH = 3  # 3 Bytes = 24 Bit

CODECS = {
    "opus": {
        # True = verarbeiten, False = überspringen
        "enabled": True,

        # Zielbitrate in Bit/s.
        # Im Skript erlaubt: 6000 bis 128000.
        # Beispiele für Mono-Sprache:
        #  8000: starke Kompression
        # 16000: mittlere Bitrate
        # 32000: guter Ausgangspunkt für hohe Sprachqualität
        "bitrate_bps": 32000,

        # Für unser Fullband-Profil fest auf 48000 Hz.
        # Die tatsächlich kodierte Audiobandbreite kann Opus
        # abhängig von Signal und Bitrate reduzieren.
        "sample_rate": 48000,

        # "voip": auf Sprache abgestimmt
        # "audio": allgemeines Audio, z. B. Sprache und Musik
        # "lowdelay": geringe algorithmische Verzögerung;
        #             verwendet keinen SILK-Modus
        "application": "voip",

        # "off": konstante Bitrate
        # "on": variable Bitrate, abhängig vom Signal
        # "constrained": begrenzt variable Bitrate
        "vbr": "off",

        # Erlaubt: 2.5, 5, 10, 20, 40, 60 Millisekunden.
        # 20 ms sind für Echtzeit-Sprachkommunikation üblich.
        # Kurze Frames reduzieren die Frame-Sammelzeit,
        # können aber die Kompressionseffizienz verringern.
        "frame_duration_ms": 20,
    },

    "amr_wb": {
        "enabled": True,

        # Erlaubte Bitraten in Bit/s:
        # 6600, 8850, 12650, 14250, 15850,
        # 18250, 19850, 23050, 23850.
        #
        # 12650 ist ein sinnvoller Ausgangspunkt
        # für HD-Mobilfunksprache.
        "bitrate_bps": 12650,

        # Durch AMR-WB vorgegeben: 16000 Hz, Mono.
        # Die Frame-Dauer ist ebenfalls fest: 20 ms.
        "sample_rate": 16000,

        # True:
        #   DTX einschalten. Die interne Sprachaktivitäts-
        #   erkennung erkennt Sprechpausen. In diesen
        #   überträgt der Codec weniger Daten und beschreibt
        #   das Hintergrundgeräusch mit SID-Frames.
        #   Der Decoder erzeugt daraus Komfortgeräusche.
        #
        # False:
        #   Sprechpausen regulär mitkodieren.
        #
        # Pausen werden NICHT aus der Aufnahme entfernt.
        # VAD und Komfortgeräusche benötigen hier keine
        # zusätzlichen Filter oder Python-Bibliotheken.
        #
        # VAD-Schwellenwert und Komfortgeräusch-Lautstärke
        # werden von diesem Encoder nicht als separate
        # Einstellungen angeboten.
        "dtx": True,
    },

    "g711_mulaw": {
        "enabled": True,

        # Fest: 64000 Bit/s bei 8000 Hz und Mono.
        # G.711 besitzt keinen Qualitäts-/Bitratenregler.
        "bitrate_bps": 64000,
        "sample_rate": 8000,

        # Keine VAD-/DTX-Simulation in diesem Profil.
        # G.711 allein bietet diese Funktionen nicht.
    },
}

AMR_WB_RATES = (
    6600, 8850, 12650, 14250, 15850,
    18250, 19850, 23050, 23850,
)


# ==================================================
# FFMPEG UND WAV
# ==================================================

def ffmpeg(executable, arguments):
    result = subprocess.run(
        [
            executable,
            "-nostdin",
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            *arguments,
        ],
        capture_output=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.decode(errors="replace").strip()
        )

    return result.stdout


def decode_to_pcm(executable, source):
    """In das gemeinsame Ausgabeformat dekodieren."""
    return ffmpeg(executable, [
        "-i", str(source),
        "-map", "0:a:0",
        "-vn",
        "-ac", str(OUTPUT_CHANNELS),
        "-ar", str(OUTPUT_RATE),
        "-c:a", "pcm_s24le",
        "-f", "s24le",
        "pipe:1",
    ])


def write_wav(path, pcm):
    """WAV mit minimalem Header ohne zusätzliche Metadaten."""
    frame_bytes = OUTPUT_CHANNELS * OUTPUT_SAMPLE_WIDTH

    if len(pcm) % frame_bytes:
        raise RuntimeError("Ungültige Länge der PCM-Daten.")

    with wave.open(str(path), "wb") as output:
        output.setnchannels(OUTPUT_CHANNELS)
        output.setsampwidth(OUTPUT_SAMPLE_WIDTH)
        output.setframerate(OUTPUT_RATE)
        output.writeframes(pcm)


# ==================================================
# PROFILE UND VALIDIERUNG
# ==================================================

def build_profiles():
    profiles = {}

    for codec, config in CODECS.items():
        if type(config["enabled"]) is not bool:
            raise ValueError(f"{codec}: enabled muss True oder False sein.")
        if not config["enabled"]:
            continue

        bitrate = config["bitrate_bps"]
        rate = config["sample_rate"]

        if type(bitrate) is not int:
            raise ValueError(
                f"{codec}: bitrate_bps muss ganzzahlig sein."
            )

        suffix = f"{codec}_{bitrate / 1000:g}kbps"

        if codec == "opus":
            if not 6000 <= bitrate <= 128000:
                raise ValueError(
                    "Opus: erlaubt sind 6000 bis 128000 Bit/s."
                )

            if rate != 48000:
                raise ValueError(
                    "Unser Opus-Profil verwendet 48000 Hz."
                )

            if config["application"] not in (
                "voip", "audio", "lowdelay"
            ):
                raise ValueError(
                    "Opus: application muss voip, audio "
                    "oder lowdelay sein."
                )

            if config["vbr"] not in (
                "off", "on", "constrained"
            ):
                raise ValueError(
                    "Opus: vbr muss off, on oder constrained sein."
                )

            if config["frame_duration_ms"] not in (
                2.5, 5, 10, 20, 40, 60
            ):
                raise ValueError(
                    "Opus: ungültige Frame-Dauer."
                )

            encoder = "libopus"
            extension = ".opus"
            options = [
                "-c:a", encoder,
                "-ar", str(rate),
                "-b:a", str(bitrate),
                "-application", config["application"],
                "-vbr", config["vbr"],
                "-frame_duration",
                str(config["frame_duration_ms"]),
            ]

        elif codec == "amr_wb":
            if bitrate not in AMR_WB_RATES:
                raise ValueError(
                    f"AMR-WB: erlaubte Bitraten: {AMR_WB_RATES}"
                )

            if rate != 16000:
                raise ValueError("AMR-WB benötigt 16000 Hz.")

            if type(config["dtx"]) is not bool:
                raise ValueError(
                    "AMR-WB: dtx muss True oder False sein."
                )

            suffix += (
                "_dtx_on" if config["dtx"] else "_dtx_off"
            )

            encoder = "libvo_amrwbenc"
            extension = ".amr"
            options = [
                "-c:a", encoder,
                "-ar", str(rate),
                "-b:a", str(bitrate),
                "-dtx", "1" if config["dtx"] else "0",
                "-f", "amr",
            ]

        elif codec == "g711_mulaw":
            if bitrate != 64000 or rate != 8000:
                raise ValueError(
                    "G.711 μ-law: dieses Profil benötigt "
                    "64000 Bit/s und 8000 Hz."
                )

            encoder = "pcm_mulaw"
            extension = ".wav"
            options = [
                "-c:a", encoder,
                "-ar", str(rate),
            ]

        else:
            raise ValueError(f"Unbekannter Codec: {codec}")

        profiles[codec] = {
            "suffix": suffix,
            "encoder": encoder,
            "extension": extension,
            "options": options,
        }

    if not profiles:
        raise ValueError(
            "Mindestens ein Codec muss aktiviert sein."
        )

    return profiles


def amr_library():
    name = os.environ.get("VC_AMRWB_LIBRARY") or ctypes.util.find_library("vo-amrwbenc")
    if not name:
        raise RuntimeError("AMR-WB: libvo-amrwbenc fehlt. Docker verwenden oder VC_AMRWB_LIBRARY auf die Bibliothek setzen.")
    try:
        lib = ctypes.CDLL(name)
        lib.E_IF_init.argtypes = []
        lib.E_IF_init.restype = ctypes.c_void_p
        lib.E_IF_encode.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                   ctypes.POINTER(ctypes.c_short),
                                   ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int]
        lib.E_IF_encode.restype = ctypes.c_int
        lib.E_IF_exit.argtypes = [ctypes.c_void_p]
        lib.E_IF_exit.restype = None
        return lib
    except (OSError, AttributeError) as exc:
        raise RuntimeError(f"AMR-WB-Bibliothek nicht verwendbar: {exc}") from exc


def encode_amr(executable, reference, encoded, config):
    lib = amr_library()
    raw = ffmpeg(executable, ["-i", str(reference), "-ac", "1", "-ar", "16000",
                              "-f", "s16le", "pipe:1"])
    state = lib.E_IF_init()
    if not state:
        raise RuntimeError("AMR-WB: Initialisierung fehlgeschlagen")
    try:
        with encoded.open("wb") as dest:
            dest.write(b"#!AMR-WB\n")
            for offset in range(0, len(raw), 640):
                chunk = raw[offset:offset + 640].ljust(640, b"\0")
                if sys.byteorder != "little":
                    chunk = b"".join(chunk[i:i+2][::-1] for i in range(0, 640, 2))
                samples = (ctypes.c_short * 320).from_buffer_copy(chunk)
                frame = (ctypes.c_ubyte * 64)()
                size = lib.E_IF_encode(state, AMR_WB_RATES.index(config["bitrate_bps"]),
                                       samples, frame, int(config["dtx"]))
                if not 0 < size <= 64:
                    raise RuntimeError(f"AMR-WB: ungültige Framegröße {size}")
                dest.write(bytes(frame[:size]))
    finally:
        lib.E_IF_exit(state)


def check_encoders(executable, profiles):
    result = subprocess.run(
        [executable, "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        check=True,
    )

    available = set()

    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0].startswith("A"):
            available.add(fields[1])

    missing = {
        profile["encoder"]
        for profile in profiles.values()
        if profile["encoder"] not in available
    }

    if "amr_wb" in profiles:
        profiles["amr_wb"]["native_library"] = "libvo_amrwbenc" not in available

    if "libvo_amrwbenc" in missing:
        amr_library()
        missing.remove("libvo_amrwbenc")

    if missing:
        raise RuntimeError(
            "FFmpeg-Encoder fehlen: "
            + ", ".join(sorted(missing))
        )


def output_filename(source, profile):
    return f"{source.stem}_{profile['suffix']}.wav"


# ==================================================
# VERARBEITUNG
# ==================================================

def process_audio(executable, source, output_dir, profiles):
    print(f"\nVerarbeite: {source.name}")

    with tempfile.TemporaryDirectory(
        prefix="speech-codecs-"
    ) as temp_dir:
        temp = Path(temp_dir)

        # Interne Referenz: wird nicht ausgegeben.
        reference_pcm = decode_to_pcm(executable, source)

        if not reference_pcm:
            raise RuntimeError(
                f"Keine Audiosamples gefunden: {source}"
            )

        reference = temp / "reference.wav"
        write_wav(reference, reference_pcm)

        for codec, profile in profiles.items():
            encoded = temp / (
                f"encoded_{codec}{profile['extension']}"
            )

            # AMR-WB direkt über die Encoderbibliothek, auch mit Standard-FFmpeg.
            if codec == "amr_wb" and profile.get("native_library", True):
                encode_amr(executable, reference, encoded, CODECS[codec])
            else:
                encode_with_ffmpeg(executable, reference, encoded, profile)

            # Bei DTX rekonstruiert der Decoder auch Komfortgeräusche.
            decoded_pcm = decode_to_pcm(executable, encoded)

            if not decoded_pcm:
                raise RuntimeError(f"Keine dekodierten Samples für {codec}.")
            # Gleiche Länge; Codec-Verzögerungen werden nicht ausgerichtet.
            target_bytes = len(reference_pcm)
            decoded_pcm = decoded_pcm[:target_bytes]
            decoded_pcm += bytes(target_bytes - len(decoded_pcm))
            filename = output_filename(source, profile)
            write_wav(temp / filename, decoded_pcm)
            print(f"  OK: {filename}")

        output_dir.mkdir(parents=True, exist_ok=True)
        for profile in profiles.values():
            filename = output_filename(source, profile)
            destination = output_dir / filename
            with (temp / filename).open("rb") as src, destination.open("xb") as dst:
                shutil.copyfileobj(src, dst)


def encode_with_ffmpeg(executable, reference, encoded, profile):
    ffmpeg(executable, [
                "-i", str(reference),
                "-map", "0:a:0",
                "-map_metadata", "-1",
                "-ac", "1",
                *profile["options"],
                str(encoded),
            ])

# ==================================================
# HAUPTPROGRAMM
# ==================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Opus, AMR-WB mit optionalem DTX und G.711 μ-law. "
            "Ausgabe: Mono, 48 kHz, 24-Bit-PCM-WAV."
        )
    )
    parser.add_argument("--ffmpeg", default=str(FFMPEG), help="FFmpeg-Pfad oder Programmname")
    parser.add_argument("--amr-dtx", choices=("on", "off"), default=None, help="AMR-WB DTX ein/aus")
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Eine oder mehrere Eingabe-Audiodateien.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT,
        help="Gemeinsamer Ausgabeordner. Standard: Output",
    )

    args = parser.parse_args()

    executable = shutil.which(args.ffmpeg)
    if executable is None:
        parser.error(
            f"FFmpeg nicht gefunden: {args.ffmpeg}. "
            "Bitte FFMPEG am Skriptanfang anpassen."
        )

    if args.amr_dtx is not None:
        CODECS["amr_wb"]["dtx"] = args.amr_dtx == "on"
    profiles = build_profiles()
    check_encoders(executable, profiles)

    inputs = [path.resolve() for path in args.inputs]
    output_dir = args.output.resolve()

    for source in inputs:
        if not source.is_file():
            parser.error(
                f"Eingabedatei nicht gefunden: {source}"
            )

    names = [source.stem.casefold() for source in inputs]
    if len(set(names)) != len(names):
        parser.error(
            "Eingabedateien müssen unterschiedliche "
            "Basisnamen haben."
        )

    if output_dir.exists() and not output_dir.is_dir():
        parser.error(
            f"Ausgabepfad ist kein Ordner: {output_dir}"
        )

    # Vorab alle Zieldateien auf Namenskonflikte prüfen.
    for source in inputs:
        for profile in profiles.values():
            destination = (
                output_dir / output_filename(source, profile)
            )
            if destination.exists() or destination.is_symlink():
                parser.error(
                    f"Datei existiert bereits: {destination}. "
                    "Anderen Ausgabeordner verwenden oder "
                    "die vorhandene Datei vorher verschieben."
                )

    for source in inputs:
        process_audio(
            executable,
            source,
            output_dir,
            profiles,
        )

    print(f"\nAlle Ergebnisse gespeichert in: {output_dir}")


if __name__ == "__main__":
    try:
        main()
    except (
        ValueError,
        RuntimeError,
        OSError,
        subprocess.CalledProcessError,
    ) as error:
        raise SystemExit(f"FEHLER: {error}")
