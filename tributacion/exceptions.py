"""Excepciones publicas del pipeline ETL."""

from __future__ import annotations


class PipelineError(Exception):
    """Error base para fallas controladas del pipeline."""


class PipelineInputError(PipelineError, ValueError):
    """Error de parametros o insumos invalidos."""


class PipelineInputFileError(PipelineInputError, FileNotFoundError):
    """Error cuando un archivo de entrada requerido no existe."""
