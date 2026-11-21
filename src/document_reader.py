from pathlib import Path
import argparse
from typing import Iterable

import pandas as pd
from pypdf import PdfReader


SUPPORTED_EXTENSIONS = {".csv", ".txt", ".pdf"}


def lire_csv(chemin: Path, nombre_lignes: int = 20) -> str:
    if nombre_lignes < 1:
        raise ValueError("Le nombre de lignes doit etre strictement positif.")
    tableau = pd.read_csv(chemin)
    lignes = tableau.head(nombre_lignes).to_string(index=False)
    nombre_total = len(tableau)
    if nombre_total > nombre_lignes:
        lignes += f"\n... {nombre_total - nombre_lignes} ligne(s) supplementaire(s)"
    return lignes


def lire_txt(chemin: Path, nombre_lignes: int = 50) -> str:
    if nombre_lignes < 1:
        raise ValueError("Le nombre de lignes doit etre strictement positif.")
    with chemin.open("r", encoding="utf-8") as fichier:
        lignes = []
        for numero, ligne in enumerate(fichier, start=1):
            if numero > nombre_lignes:
                lignes.append("... fichier partiellement affiche")
                break
            lignes.append(ligne.rstrip("\n"))
    return "\n".join(lignes)


def lire_pdf(chemin: Path, nombre_pages: int = 5) -> str:
    if nombre_pages < 1:
        raise ValueError("Le nombre de pages doit etre strictement positif.")
    lecteur = PdfReader(str(chemin))
    morceaux = []
    for index, page in enumerate(lecteur.pages[:nombre_pages], start=1):
        texte = page.extract_text() or ""
        morceaux.append(f"--- Page {index} ---\n{texte.strip()}")
    if len(lecteur.pages) > nombre_pages:
        morceaux.append(
            f"... {len(lecteur.pages) - nombre_pages} page(s) supplementaire(s)"
        )
    return "\n\n".join(morceaux)


def lire_document(chemin: str | Path) -> str:
    chemin = Path(chemin).expanduser()
    if not chemin.is_file():
        raise FileNotFoundError(f"Fichier introuvable : {chemin}")

    extension = chemin.suffix.lower()
    if extension == ".csv":
        return lire_csv(chemin)
    if extension == ".txt":
        return lire_txt(chemin)
    if extension == ".pdf":
        return lire_pdf(chemin)
    raise ValueError(
        f"Format non pris en charge : {extension or '(sans extension)'}. "
        "Formats acceptes : CSV, TXT, PDF."
    )


def trouver_documents(racine: Path) -> list[Path]:
    return sorted(
        (
            chemin
            for chemin in racine.rglob("*")
            if chemin.is_file()
            and chemin.suffix.lower() in SUPPORTED_EXTENSIONS
            and ".git" not in chemin.parts
            and ".venv" not in chemin.parts
        ),
        key=lambda chemin: str(chemin).lower(),
    )


def menu(racine: Path) -> None:
    while True:
        documents = trouver_documents(racine)
        print("\nLecteur de documents")
        if not documents:
            print("Aucun document CSV, TXT ou PDF trouve.")
        else:
            for index, chemin in enumerate(documents, start=1):
                print(f"{index}. {chemin.relative_to(racine)}")
        print("0. Quitter")

        choix = input("\nChoisissez un document : ").strip()
        if choix == "0":
            return
        if not choix.isdigit():
            print("Saisie invalide.")
            continue
        index = int(choix)
        if not 1 <= index <= len(documents):
            print("Numero hors liste.")
            continue
        try:
            print(f"\n{documents[index - 1].relative_to(racine)}")
            print(lire_document(documents[index - 1]))
        except (ValueError, FileNotFoundError, OSError) as erreur:
            print(f"Erreur : {erreur}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lire un fichier CSV, TXT ou PDF depuis le terminal."
    )
    parser.add_argument("chemin", nargs="?", help="Chemin du document")
    arguments = parser.parse_args()

    if arguments.chemin:
        chemin = Path(arguments.chemin).expanduser()
        try:
            print(lire_document(chemin))
        except (ValueError, FileNotFoundError, OSError) as erreur:
            raise SystemExit(str(erreur)) from erreur
    else:
        racine = Path(__file__).resolve().parent.parent
        menu(racine)


if __name__ == "__main__":
    main()
