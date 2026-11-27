"""Directional ABI rules for changed fields on an observed dynamic symbol."""

TYPE_RULES = (
    (lambda kinds: 'TLS' in kinds, 'INCOMPATIBLE', 'HIGH', 'TLS_KIND_CHANGED'),
    (lambda kinds: 'FUNC' in kinds and bool(kinds & {'IFUNC', 'GNU_IFUNC'}), 'UNKNOWN', 'LOW', 'IFUNC_TRANSITION'),
    (lambda kinds: 'NOTYPE' in kinds and bool(kinds & {'FUNC', 'OBJECT'}), 'UNKNOWN', 'MEDIUM', 'NOTYPE_ANNOTATION'),
)


def classify_symbol_change(field, before, after):
    if field == 'type':
        for matches, status, severity, reason in TYPE_RULES:
            if matches({before,after}):
                return status, severity, reason
        return 'INCOMPATIBLE', 'HIGH', 'KIND_CHANGED'
    if field == 'size':
        return 'INCOMPATIBLE', 'HIGH', 'DATA_SIZE_DECREASED' if after < before else 'DATA_SIZE_INCREASED'
    if field == 'binding' and before in ('GNU_UNIQUE','UNIQUE') and after == 'GLOBAL':
        return 'UNKNOWN', 'MEDIUM', 'GNU_UNIQUE_DROPPED'
    return 'UNKNOWN', 'HIGH', 'SYMBOL_'+field.upper()+'_CHANGED'
