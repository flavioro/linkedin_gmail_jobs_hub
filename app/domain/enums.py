from enum import StrEnum


class JobStatus(StrEnum):
    NEW = "new"
    DUPLICATE = "duplicate"
    PARSE_FAILED = "parse_failed"
    IGNORED = "ignored"


class WorkModel(StrEnum):
    REMOTO = "remoto"
    HIBRIDO = "hibrido"
    PRESENCIAL = "presencial"
    NAO_INFORMADO = "nao_informado"


class Seniority(StrEnum):
    ESTAGIO = "estagio"
    JUNIOR = "junior"
    PLENO = "pleno"
    SENIOR = "senior"
    ESPECIALISTA = "especialista"
    NAO_INFORMADO = "nao_informado"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
