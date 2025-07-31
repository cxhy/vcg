#!/usr/bin/env python3
class VCGError(Exception):
    pass

class VCGFileError(VCGError):
    pass

class VCGParseError(VCGError):
    pass

class VCGSyntaxError(VCGError):
    pass

class VCGRuntimeError(VCGError):
    pass