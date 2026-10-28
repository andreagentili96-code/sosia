"""Riconoscitori a modello (facoltativi). Le regole funzionano da sole; un modello NER locale aggiunge
nomi e luoghi che i dizionari non conoscono. Solo CPU, mai in rete.

Contratto: un oggetto con `riconosci(testo) -> list[dict]`, ogni dict con
tipo («PERSONA», «LUOGO», «ORGANIZZAZIONE»), inizio, fine, punteggio (0-1).

GLiNER (urchade/gliner_multi_pii-v1, Apache-2.0) si carica da cartelle locali:
- il modello: SOSIA_GLINER  (predefinito <SOSIA_MODELLI>/gliner_multi_pii-v1)
- il vocabolario del modello base mdeberta-v3-base: SOSIA_MDEBERTA (predefinito <SOSIA_MODELLI>/mdeberta-v3-base)
SOSIA_MODELLI, se non è impostata, vale %LOCALAPPDATA%\\sosia\\modelli-origine su Windows e
~/.local/share/sosia/modelli-origine altrove: è la cartella in cui scrive scripts/download_models.py.
Il file di configurazione di GLiNER punta a «microsoft/mdeberta-v3-base» su Internet: si prepara una cartella
derivata in %LOCALAPPDATA%\\sosia\\modelli con un collegamento fisico ai pesi (nessuna copia da 1,1 GB),
la configurazione che punta al percorso locale e un tokenizer.json costruito dallo spm.model con sentencepiece
(non serve protobuf). HF_HUB_OFFLINE e TRANSFORMERS_OFFLINE sono forzati a 1.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path


def cartella_modelli() -> Path:
    """Cartella dei modelli scaricati dall'utente (Sosia non scarica mai nulla mentre lavora)."""
    if os.environ.get("SOSIA_MODELLI"):
        return Path(os.environ["SOSIA_MODELLI"])
    base = Path(os.environ["LOCALAPPDATA"]) if os.environ.get("LOCALAPPDATA") else Path.home() / ".local" / "share"
    return base / "sosia" / "modelli-origine"


GLINER_PREDEFINITO = cartella_modelli() / "gliner_multi_pii-v1"
MDEBERTA_PREDEFINITO = cartella_modelli() / "mdeberta-v3-base"


def _offline():
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def costruisci_tokenizer(spm_model: Path, uscita: Path):
    """tokenizer.json «veloce» equivalente a DebertaV2 (mdeberta) senza protobuf.
    Approssimazione dichiarata: la normalizzazione precompilata di SentencePiece è sostituita da NFKC."""
    import sentencepiece as spm
    from tokenizers import Regex, Tokenizer, decoders, models, normalizers, pre_tokenizers, processors
    sp = spm.SentencePieceProcessor(model_file=str(spm_model))
    vocab = [(sp.id_to_piece(i), sp.get_score(i)) for i in range(sp.get_piece_size())]
    vocab.append(("[MASK]", 0.0))
    tk = Tokenizer(models.Unigram(vocab, unk_id=sp.unk_id(), byte_fallback=False))
    tk.normalizer = normalizers.Sequence([normalizers.Strip(), normalizers.NFKC(), normalizers.Replace(Regex(" {2,}"), " ")])
    tk.pre_tokenizer = pre_tokenizers.Metaspace(replacement="▁", prepend_scheme="always")
    tk.decoder = decoders.Metaspace(replacement="▁", prepend_scheme="always")
    cls_id, sep_id = sp.piece_to_id("[CLS]"), sp.piece_to_id("[SEP]")
    tk.post_processor = processors.TemplateProcessing(
        single="[CLS]:0 $A:0 [SEP]:0", pair="[CLS]:0 $A:0 [SEP]:0 $B:1 [SEP]:1",
        special_tokens=[("[CLS]", cls_id), ("[SEP]", sep_id)])
    uscita.mkdir(parents=True, exist_ok=True)
    tk.save(str(uscita / "tokenizer.json"))
    speciali = {"bos_token": "[CLS]", "eos_token": "[SEP]", "unk_token": "[UNK]", "sep_token": "[SEP]",
                "pad_token": "[PAD]", "cls_token": "[CLS]", "mask_token": "[MASK]"}
    (uscita / "tokenizer_config.json").write_text(json.dumps(
        {"tokenizer_class": "PreTrainedTokenizerFast", "do_lower_case": False, "model_max_length": 512, **speciali},
        indent=1), encoding="utf-8")
    (uscita / "special_tokens_map.json").write_text(json.dumps(speciali, indent=1), encoding="utf-8")


def prepara_gliner(modello: Path | None = None, base: Path | None = None) -> Path:
    modello = Path(os.environ.get("SOSIA_GLINER") or modello or GLINER_PREDEFINITO)
    base = Path(os.environ.get("SOSIA_MDEBERTA") or base or MDEBERTA_PREDEFINITO)
    if not (modello / "pytorch_model.bin").exists():
        raise FileNotFoundError(f"pesi di GLiNER non trovati in {modello}")
    derivata = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "sosia" / "modelli" / modello.name
    derivata.mkdir(parents=True, exist_ok=True)
    pesi = derivata / "pytorch_model.bin"
    if not pesi.exists() or pesi.stat().st_size != (modello / "pytorch_model.bin").stat().st_size:
        if pesi.exists():
            pesi.unlink()
        try:
            os.link(modello / "pytorch_model.bin", pesi)  # collegamento fisico: zero spazio in più
        except OSError:
            shutil.copy2(modello / "pytorch_model.bin", pesi)
    cfg = json.loads((modello / "gliner_config.json").read_text(encoding="utf-8"))
    cfg["model_name"] = str(derivata)  # config e tokenizer del modello base presi dalla cartella derivata
    (derivata / "gliner_config.json").write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    cfg_base = json.loads((base / "config.json").read_text(encoding="utf-8"))
    (derivata / "config.json").write_text(json.dumps(cfg_base, indent=1), encoding="utf-8")
    if not (derivata / "tokenizer.json").exists():
        costruisci_tokenizer(base / "spm.model", derivata)
    return derivata


class SpacyNER:
    """spaCy con un modello italiano (es. it_core_news_md). Etichette PER, LOC, ORG. Non installato."""

    MAPPA = {"PER": "PERSONA", "LOC": "LUOGO", "GPE": "LUOGO", "ORG": "ORGANIZZAZIONE"}

    def __init__(self, modello: str = "it_core_news_md"):
        import spacy
        self.nlp = spacy.load(modello, disable=["parser", "lemmatizer"])

    def riconosci(self, testo: str) -> list[dict]:
        return [{"tipo": self.MAPPA[e.label_], "inizio": e.start_char, "fine": e.end_char, "punteggio": 0.8}
                for e in self.nlp(testo).ents if e.label_ in self.MAPPA]


class GlinerNER:
    """GLiNER su CPU. Etichette in italiano; il testo si spezza in finestre di righe (max ~1200 caratteri)."""

    ETICHETTE = {"persona": "PERSONA", "nome di persona": "PERSONA", "soprannome": "PERSONA",
                 "città": "LUOGO", "paese o frazione": "LUOGO", "organizzazione": "ORGANIZZAZIONE",
                 "numero di serie": "CODICE", "numero di documento": "CODICE", "codice identificativo": "CODICE",
                 "numero di pratica": "CODICE", "matricola": "CODICE"}
    # soglie per etichetta (0.5.0): le persone si prendono anche incerte (una fuga costa più di un falso positivo),
    # organizzazioni e codici solo se il modello è sicuro
    SOGLIE = {"persona": 0.4, "nome di persona": 0.4, "soprannome": 0.55, "città": 0.45, "paese o frazione": 0.45,
              "organizzazione": 0.6, "numero di serie": 0.6, "numero di documento": 0.55, "codice identificativo": 0.6,
              "numero di pratica": 0.55, "matricola": 0.55}

    def __init__(self, percorso: str | None = None, soglia: float = 0.5, thread: int | None = None):
        _offline()
        import warnings
        warnings.filterwarnings("ignore")
        import torch
        torch.set_num_threads(thread or max(1, min(8, (os.cpu_count() or 4) // 2)))
        from gliner import GLiNER
        cartella = prepara_gliner(Path(percorso)) if percorso else prepara_gliner()
        self.m = GLiNER.from_pretrained(str(cartella), local_files_only=True, load_tokenizer=True)
        self.m.eval()
        self.soglia = soglia

    def _finestre(self, testo: str, massimo: int = 1200):
        inizio = 0
        while inizio < len(testo):
            fine = min(len(testo), inizio + massimo)
            if fine < len(testo):
                taglio = testo.rfind("\n", inizio + massimo // 2, fine)
                if taglio < 0:
                    taglio = testo.rfind(" ", inizio + massimo // 2, fine)
                fine = taglio + 1 if taglio > 0 else fine
            yield inizio, testo[inizio:fine]
            inizio = fine

    def riconosci(self, testo: str) -> list[dict]:
        out = []
        for base, parte in self._finestre(testo):
            if not parte.strip():
                continue
            minima = min(min(self.SOGLIE.values()), self.soglia)
            for e in self.m.predict_entities(parte, list(self.ETICHETTE), threshold=minima):
                if e["score"] < self.SOGLIE.get(e["label"], self.soglia):
                    continue
                a, b = base + e["start"], base + e["end"]
                if re.fullmatch(r"\W*", testo[a:b]):
                    continue
                out.append({"tipo": self.ETICHETTE[e["label"]], "inizio": a, "fine": b, "punteggio": float(e["score"])})
        return out


_CACHE: dict = {}


def carica(nome: str | None):
    """«gliner», «gliner:/cartella/locale», «spacy», «spacy:it_core_news_sm» oppure None. Il modello resta in memoria."""
    if not nome:
        return None
    if nome in _CACHE:
        return _CACHE[nome]
    tipo, _, arg = nome.partition(":")
    if tipo == "spacy":
        r = SpacyNER(arg or "it_core_news_md")
    elif tipo == "gliner":
        r = GlinerNER(arg or None)
    else:
        raise ValueError(f"riconoscitore sconosciuto: {nome}")
    _CACHE[nome] = r
    return r
