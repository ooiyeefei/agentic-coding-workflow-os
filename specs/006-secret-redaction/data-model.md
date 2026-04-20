# Data Model: Secret Redaction

## BuiltInPattern

- **Purpose**: Represents one shipped secret-detection rule.
- **Fields**:
  - `name`: Stable marker family name such as `openai-key` or `bearer-token`
  - `pattern`: Regex used to detect the secret-bearing substring or subcomponent
  - `replacement_mode`: Whether the rule replaces the full match or selected capture groups
- **Validation rules**:
  - `name` must be stable and safe to embed in `[REDACTED:<pattern-name>]`.
  - Rules are applied in a deterministic order from more specific to more general patterns.

## RedactionMarker

- **Purpose**: Represents the visible placeholder inserted into the output string.
- **Fields**:
  - `pattern_name`: The family name that triggered the redaction
  - `text`: The rendered marker string, always in the form `[REDACTED:<pattern-name>]`
- **Validation rules**:
  - Markers must be idempotent and should not themselves match secret patterns.
  - Marker text must remain readable in logs and markdown artifacts.

## ExtraPattern

- **Purpose**: Represents one caller-provided regex appended to the built-in catalog for a single call.
- **Fields**:
  - `pattern`: Raw regex string supplied by the caller
  - `pattern_name`: Stable derived label `extra-pattern-N` based on list order
- **Validation rules**:
  - List order defines the stable marker label for the duration of the call.
  - Extra patterns run after the built-in catalog so custom coverage extends, rather than destabilizes, the default behavior.

## RedactionPass

- **Purpose**: Describes one end-to-end transformation of an input string.
- **Fields**:
  - `input_text`: Original string supplied by the caller
  - `output_text`: Redacted string returned to the caller
  - `applied_pattern_names`: Ordered set of marker families that modified the text
- **Validation rules**:
  - Safe input may produce identical input and output.
  - A second pass over already redacted output should preserve readability and avoid nested marker corruption.
