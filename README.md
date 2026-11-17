# vc-speech-codec

Sprachaufnahmen mit Opus, AMR-WB und G.711 μ-law kodieren und wieder zu einheitlichen WAV-Dateien dekodieren. Grundlage ist das mitgebrachte `process.py`. Keine zusätzlichen Python-Pakete erforderlich (Python 3.10 oder neuer).

Die Einstellungen stehen oben in `process.py` in `CODECS`. Alle Codecs sind standardmäßig aktiv:

| Profil | Kodierung | Standard |
| --- | --- | --- |
| Opus | Mono, 48 kHz | 32 kbit/s, `voip`, CBR, 20-ms-Frames |
| AMR-WB | Mono, 16 kHz, 20-ms-Frames | 12,65 kbit/s, DTX an |
| G.711 μ-law | Mono, 8 kHz | feste 64 kbit/s |

**Ausgabe immer: Mono, 48 kHz, 24-Bit-PCM-WAV.** Die höhere Ausgabeabtastrate stellt keine beim Codec verlorenen Frequenzen wieder her. Alle Dateien liegen direkt in `Output`; interne Referenz- und Codecdateien bleiben temporär und werden entfernt.

Für `aufnahme.wav` entstehen:

```text
Output/aufnahme_opus_32kbps.wav
Output/aufnahme_amr_wb_12.65kbps_dtx_on.wav
Output/aufnahme_g711_mulaw_64kbps.wav
```

## Codec-Vergleich

Die Werte „bei uns“ beschreiben die Standardkonfiguration dieses Projekts, nicht sämtliche Möglichkeiten der Standards. AMR-WB ist auch als **ITU-T G.722.2** standardisiert; es ist nicht mit G.722 gleichzusetzen.

| Eigenschaft | Opus | AMR-WB / G.722.2 | G.711 μ-law |
| --- | --- | --- | --- |
| Typische Anwendung | Internet-Telefonie, WebRTC, Videokonferenzen und Sprachchats | HD-Mobilfunktelefonie, insbesondere VoLTE | Klassische Telefonie, SIP, Telefonanlagen und Gateways; μ-law besonders in Nordamerika und Japan |
| Abtastrate beim Kodieren | **48 kHz** | **16 kHz** | **8 kHz** |
| Audiobandbreite | Abhängig von Modus, Signal und Bitrate bis etwa 20 kHz | Etwa 50–7000 Hz | Typischer Telefonbereich etwa 300–3400 Hz¹ |
| Gewählte Bitrate | **32 kbit/s** | **12,65 kbit/s** | **64 kbit/s**, fest |
| Bitrate einstellbar | Im Skript: 6–128 kbit/s | 6,60; 8,85; 12,65; 14,25; 15,85; 18,25; 19,85; 23,05; 23,85 kbit/s | Nein |
| Bitratensteuerung bei uns | Konstant: `vbr="off"` | Fester Sprachmodus; DTX reduziert die durchschnittliche Datenmenge in Pausen | Konstant |
| Anwendungsmodus bei uns | `voip`: auf Sprache abgestimmt | Sprachcodec | Telefonieprofil |
| Frame-Dauer bei uns | **20 ms** | **20 ms**, fest | Samplebasiert; keine feste Codec-Frame-Dauer |
| Frame-Dauer einstellbar | Im Skript: 2,5; 5; 10; 20; 40; 60 ms | Nein | Nicht anwendbar |
| VAD – Sprachaktivitätserkennung | Keine separate VAD-/DTX-Einstellung im Skript | Intern aktiv im Rahmen von DTX | Nicht implementiert |
| DTX – reduzierte Übertragung in Sprechpausen | Nicht aktiviert | **Aktiviert: `dtx=True`**, abschaltbar | Nicht implementiert |
| Komfortgeräusche | Keine gesonderte Komfortgeräuschfunktion aktiviert | Automatisch vom Decoder erzeugt, basierend auf den Hintergrundbeschreibungen des Encoders (SID-Frames) | Nicht implementiert |
| Verwendeter Encoder | FFmpeg: `libopus` | Im Docker-Image: Bibliothek `libvo-amrwbenc` direkt über Python `ctypes`; alternativ FFmpeg: `libvo_amrwbenc` | FFmpeg: `pcm_mulaw` |

¹ 300–3400 Hz beschreibt den üblichen Telefon-Sprachkanal, keine durch μ-law selbst erzwungene Filtergrenze. Beim Resampling auf 8 kHz begrenzt der Anti-Aliasing-Filter den oberen Frequenzbereich auf unter 4 kHz; eine untere Grenze von 300 Hz ergibt sich daraus nicht. Für den Codec-Durchlauf ist kein zusätzlicher Telefonbandfilter nötig. Ein solcher Filter wäre eine zusätzliche Modellierung eines Telefonkanals und wird hier nicht angewendet. Die Kodier-Abtastraten in der Tabelle sind von der gemeinsamen WAV-Ausgabe mit 48 kHz zu unterscheiden.

### Offizielle Quellen und Websites

- [Opus – offizielle Projektwebsite](https://opus-codec.org/): Überblick zum Codec und zur Referenzimplementierung.
- [IETF RFC 6716 – Definition of the Opus Audio Codec](https://www.rfc-editor.org/rfc/rfc6716.html): Opus-Spezifikation, Bandbreiten, Betriebsarten und Frame-Struktur. Die im Skript erlaubten Bitraten und Frame-Dauern sind ein Projektprofil und keine vollständige Aufzählung aller Opus-Möglichkeiten.
- [ITU-T G.722.2 – AMR-WB](https://www.itu.int/rec/T-REC-G.722.2/en): Standard für die breitbandige Sprachkodierung mit etwa 7 kHz Audiobandbreite.
- [IETF RFC 4867 – RTP Payload Format für AMR und AMR-WB](https://www.rfc-editor.org/rfc/rfc4867.html): AMR-WB-Modi, 20-ms-Sprachframes, SID-Frames und DTX-Kontext. Das Projekt erzeugt keine RTP-Pakete; die Quelle dient zur Einordnung der Codec-Eigenschaften.
- [ITU-T G.711 – Pulse code modulation of voice frequencies](https://www.itu.int/rec/T-REC-G.711/en): Standard für A-law/μ-law und die 64-kbit/s-Kodierung; dieses Projekt verwendet μ-law.
- [FFmpeg – offizielle Codec-Dokumentation](https://ffmpeg.org/ffmpeg-codecs.html): Encoder und Optionen, insbesondere `libopus` und `libvo-amrwbenc`. Die Verfügbarkeit einzelner Encoder hängt vom FFmpeg-Build ab.

## Windows und macOS: gemeinsamer Weg mit Docker

1. Git und Docker Desktop installieren (offizielle Anbieter: https://git-scm.com und https://www.docker.com/products/docker-desktop/). Unter Windows das WSL-2-Backend aktivieren; Docker Desktop starten. Auf macOS die zur CPU passende Version installieren.
2. Repository klonen und in dessen Ordner wechseln:

```sh
git clone https://github.com/Sebastian-Schwarze/vc-speech-codec.git
cd vc-speech-codec
docker build -t vc-speech-codec .
```

3. Einen Ordner `Input` anlegen und Audiodateien hineinkopieren. Dann starten.

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force Input, Output
docker run --rm --mount "type=bind,source=$($PWD.Path),target=/data" vc-speech-codec "Input/aufnahme.wav"
```

macOS Terminal:

```sh
mkdir -p Input Output
docker run --rm --mount "type=bind,source=$(pwd),target=/data" vc-speech-codec "Input/aufnahme.wav"
```

Mehrere Dateien als einzelne Argumente angeben (`Input/a.wav Input/b.wav`). Docker expandiert `Input/*.wav` im Container nicht automatisch. Pfade mit Leerzeichen in Anführungszeichen setzen. Eingaben müssen innerhalb des eingebundenen Projektordners liegen. Ergebnisse erscheinen im lokalen `Output`. Es wird kein Server gestartet.

Nach Änderungen an `process.py` das Image erneut bauen. Ein Image enthält FFmpeg und `libvo-amrwbenc`; ein speziell kompiliertes FFmpeg ist damit nicht nötig. Beim Teilen eines Images dieselbe Image-ID bzw. denselben Registry-Digest verwenden: Debian- und Paketupdates können das Ergebnis eines späteren Neubaus ändern.

Zum Neubauen im Projektordner `vc-speech-codec` (dort, wo das `Dockerfile` liegt) ausführen:

```sh
docker build -t vc-speech-codec .
```

Danach die Verarbeitung mit dem oben gezeigten `docker run`-Befehl erneut starten. Der neue Container verwendet das aktualisierte Image mit der geänderten `process.py`. Für Skriptänderungen ist kein `--no-cache` erforderlich; Docker übernimmt die geänderte Datei beim Neubau automatisch.

## Lokale Installation mit Anaconda / Miniconda

In Anaconda Prompt (Windows) oder Terminal (macOS) im Projektordner:

```sh
conda env create -f environment.yml
conda activate vc-speech-codec
python process.py Input/aufnahme.wav
```

`environment.yml` installiert Python 3.12 und FFmpeg von conda-forge. AMR-WB benötigt **zusätzlich** entweder ein FFmpeg mit `libvo_amrwbenc` oder eine ladbare `libvo-amrwbenc`-Bibliothek. Ein normales FFmpeg-Paket enthält diesen Encoder häufig nicht. Die Verfügbarkeit ist vom Betriebssystem und Build abhängig; die Conda-Umgebung allein garantiert deshalb keinen vollständigen AMR-WB-Workflow.

- **Windows:** Für alle drei Codecs Docker verwenden. Ein bereits vorhandenes selbst gebautes FFmpeg mit `libvo_amrwbenc` kann über `--ffmpeg "C:\\Tools\\ffmpeg.exe"` eingebunden werden. Eine separat vorhandene, vertrauenswürdige Encoder-DLL kann alternativ per `VC_AMRWB_LIBRARY` angegeben werden; Architektur und Python müssen zusammenpassen.
- **macOS:** Alternativ mit Homebrew `brew install ffmpeg vo-amrwbenc` installieren und `python process.py --ffmpeg "$(brew --prefix)/bin/ffmpeg" Input/aufnahme.wav` starten. Falls die Bibliothek nicht automatisch gefunden wird: `export VC_AMRWB_LIBRARY="$(brew --prefix vo-amrwbenc)/lib/libvo-amrwbenc.dylib"`. Ein vorhandenes eigenes FFmpeg kann ebenfalls mit `--ffmpeg` gewählt werden.
- **Debian/Ubuntu:** `sudo apt-get install python3 ffmpeg libvo-amrwbenc0`, danach `python3 process.py Input/aufnahme.wav`.

FFmpeg-Auswahl: `--ffmpeg` überschreibt die Umgebungsvariable `FFMPEG`, sonst wird `ffmpeg` im PATH gesucht. Vor der Verarbeitung prüft das Skript die aktivierten Encoder; fehlende Voraussetzungen führen zu einer Fehlermeldung. Ein AMR-WB-Decoder muss ebenfalls im verwendeten FFmpeg vorhanden sein.

Native Windows-/macOS-Installationen sind hier nicht ausgeführt worden. Der gemeinsame Linux-Docker-Weg wird separat funktional getestet.

## Einstellungen und erlaubte Werte

Im Python-Wörterbuch `CODECS` ändern; boolesche Werte heißen dort `True` und `False`. **Auch DTX wird direkt dort eingestellt:** Unter `amr_wb` bedeutet `"dtx": True` eingeschaltet und `"dtx": False` ausgeschaltet. Ein zusätzlicher Befehl ist dafür nicht erforderlich. Die optionale CLI-Option `--amr-dtx on` bzw. `--amr-dtx off` überschreibt diesen Wert nur für den jeweiligen Aufruf. Ohne diese Option gilt die Skripteinstellung. Bei Docker nach einer Skriptänderung das Image neu bauen. Weitere CLI-Optionen mit `python process.py --help` anzeigen.

| Einstellung | Bedeutung | Erlaubt / Standard |
| --- | --- | --- |
| `enabled` je Codec | Profil verarbeiten | `True` / `False`; Standard `True`; mindestens eins aktiv |
| Opus `bitrate_bps` | Zielbitrate in Bit/s | ganze Zahl 6000–128000; Standard 32000 |
| Opus `sample_rate` | Encoder-Eingangsrate | fest 48000 Hz in diesem Profil |
| Opus `application` | Sprach-, allgemeine Audio- oder Verzögerungsoptimierung | `voip` (Standard), `audio`, `lowdelay` |
| Opus `vbr` | konstante, variable oder begrenzt variable Bitrate | `off` (CBR, Standard), `on`, `constrained` |
| Opus `frame_duration_ms` | Audiodauer pro Frame | 2.5, 5, 10, 20 (Standard), 40, 60 ms |
| AMR-WB `bitrate_bps` | Modus / Sprachbitrate | 6600, 8850, 12650 (Standard), 14250, 15850, 18250, 19850, 23050, 23850 |
| AMR-WB `sample_rate` | Encoder-Eingangsrate | fest 16000 Hz |
| AMR-WB `dtx` | Sprachaktivitätserkennung und reduzierte Übertragung in Pausen | `True` (Standard) / `False`; CLI `--amr-dtx on` / `off` überschreibt |
| G.711 `bitrate_bps` / `sample_rate` | feste μ-law-Einstellungen | 64000 / 8000 |
| `--output` | gemeinsamer Zielordner | beliebiger beschreibbarer Ordner; Standard `Output` |
| `--ffmpeg` | FFmpeg-Programm | Programmname oder ausführbarer Pfad |
| `VC_AMRWB_LIBRARY` | alternative Encoderbibliothek | Bibliothekspfad; nur bei Bibliotheksbetrieb |

DTX entfernt keine Pausen. SID-Frames beschreiben Hintergrundgeräusche; der Decoder erzeugt Komfortgeräusche. VAD-Schwelle und Komfortgeräuschpegel sind hier nicht separat einstellbar. G.711 hat keine DTX-Simulation. Die angegebene Bitrate ist die Codec-Zielbitrate, nicht die Bitrate der abschließenden PCM-WAV-Datei; DTX reduziert die mittlere AMR-Datenrate.

## Verarbeitung und Grenzen

FFmpeg liest die erste Audiospur der angegebenen Dateien. Stereo wird zu Mono gemischt. Die Dekodateien erhalten dieselbe Sampleanzahl wie die intern auf 48 kHz umgerechnete Eingabe: Endpadding wird abgeschnitten oder durch Stille ergänzt. Das ist keine automatische zeitliche Ausrichtung von Codec-Verzögerungen. Lange Aufnahmen benötigen entsprechend RAM, weil das ursprüngliche Skript PCM-Daten im Speicher verarbeitet. WAV-Dateien über der RIFF-Größengrenze werden nicht unterstützt.

Gleiche Basisnamen werden unabhängig von Groß-/Kleinschreibung abgewiesen. Vorhandene Zieldateien werden nicht überschrieben. Erst wenn alle Codec-Durchläufe einer Eingabe erfolgreich sind, werden deren WAVs kopiert. Ein kompletter Batch ist keine Transaktion: bei späteren Eingabefehlern bleiben frühere Ergebnisse erhalten; auch Schreibfehler können bereits kopierte Dateien hinterlassen. Codec-/Bitratenname und AMR-DTX stehen im Dateinamen; andere Profiländerungen erfordern einen anderen Ausgabeordner, um die Versuche sauber zu trennen.

## Tests

Im Projektordner mit vollständig installierten Audiowerkzeugen:

```sh
python -m unittest discover -s tests -v
```

Im Docker-Image:

```sh
docker run --rm --entrypoint python3 -w /app vc-speech-codec -m unittest discover -s tests -v
```

Die Tests erzeugen synthetische Audiosignale und prüfen alle drei Codec-Durchläufe, WAV-Format und Länge, Dateinamen, DTX-Wirkung auf Stille, ungültige Einstellungen, beschädigte Eingaben sowie den Überschreibschutz. Keine Testdaten werden in `Output` gespeichert.
