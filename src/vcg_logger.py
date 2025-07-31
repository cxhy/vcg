#!/usr/bin/env python3
import logging
import sys
from pathlib import Path
from typing import Optional, Union
from contextvars import ContextVar

current_file_context: ContextVar[Optional[str]] = ContextVar('current_file_context', default=None)

class FileContextFormatter(logging.Formatter):
    
    def format(self, record):
        file_context = current_file_context.get()
        
        if file_context:
            record.file_context = f"[{file_context}]"
        else:
            record.file_context = ""
        
        return super().format(record)

class VCGLoggerManager:
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.logger = logging.getLogger('VCG')
            self.console_handler = None
            self.file_handler = None
            self._setup_formatters()
            VCGLoggerManager._initialized = True
    
    def _setup_formatters(self):
        self.console_formatter = FileContextFormatter(
            fmt='[VCG-%(levelname)s] %(file_context)s %(name)s: %(message)s'
        )
        
        self.file_formatter = FileContextFormatter(
            fmt='%(asctime)s [%(levelname)s] %(file_context)s %(name)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        self.detailed_console_formatter = FileContextFormatter(
            fmt='[VCG-%(levelname)s] %(file_context)s %(name)s:%(lineno)d - %(message)s'
        )
    
    def setup_logger(self, 
                    level: Union[int, str] = logging.WARNING,
                    log_file: Optional[Union[str, Path]] = None,
                    quiet: bool = False):
        
        self.logger.handlers.clear()
    
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)        
        
        self.logger.setLevel(level)

        self.console_handler = logging.StreamHandler(sys.stderr)
        
        if quiet:
            self.console_handler.setLevel(logging.ERROR)
        else:
            self.console_handler.setLevel(level)

        if level <= logging.DEBUG:
            self.console_handler.setFormatter(self.detailed_console_formatter)
        else:
            self.console_handler.setFormatter(self.console_formatter)

        self.logger.addHandler(self.console_handler)

        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self.file_handler = logging.FileHandler(log_path, mode='w', encoding='utf-8')
            self.file_handler.setLevel(logging.DEBUG)
            self.file_handler.setFormatter(self.file_formatter)

            self.logger.addHandler(self.file_handler)

    
    def get_logger(self, name: str = '') -> logging.Logger:
        if name:
            return logging.getLogger(f'VCG.{name}')
        return self.logger
    
    def set_file_context(self, file_path: Union[str, Path]):
        if file_path:
            file_name = Path(file_path).name
            current_file_context.set(file_name)
        else:
            current_file_context.set(None)
    
    def clear_file_context(self):
        current_file_context.set(None)

vcg_logger_manager = VCGLoggerManager()

def get_vcg_logger(name: str = '') -> logging.Logger:
    return vcg_logger_manager.get_logger(name)

def setup_vcg_logging(**kwargs):
    return vcg_logger_manager.setup_logger(**kwargs)

def set_file_context(file_path: Union[str, Path]):
    return vcg_logger_manager.set_file_context(file_path)

def clear_file_context():
    return vcg_logger_manager.clear_file_context()