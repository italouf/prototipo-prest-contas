import unicodedata


def normalizar_nome(nome):
    return " ".join(unicodedata.normalize("NFKC", nome).casefold().split())


PILARES = ("PDI", "FORMACAO", "STARTUPS")
