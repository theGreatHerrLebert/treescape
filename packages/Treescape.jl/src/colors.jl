# Host-side color parsing and Python-compatible formatting
# (docs/conventions.md, "Host semantics mirrored from plot.py").

const RGBA = NTuple{4,UInt8}

"""
    parse_color(spec) -> NTuple{4,UInt8}

`"#rrggbb"`, `"#rrggbbaa"` (leading `#`s stripped), or a 3-/4-tuple of
reals truncated toward zero, as Python's `int()`. Matches `plot.py`'s
`_parse_color` on well-formed input.
"""
function parse_color(spec::AbstractString)
    s = lstrip(spec, '#')
    if (length(s) == 6 || length(s) == 8) && all(isxdigit, s)
        bytes = [parse(UInt8, s[i:(i + 1)]; base=16) for i in 1:2:length(s)]
        return length(bytes) == 3 ? (bytes..., 0xff) : Tuple(bytes)
    end
    length(s) in (6, 8) && throw(ArgumentError("invalid hex color $(pyrepr(spec))"))
    throw(ArgumentError("hex color must be #rrggbb or #rrggbbaa; got $(pyrepr(spec))"))
end

function parse_color(spec::Tuple)
    length(spec) in (3, 4) || throw(ArgumentError("color tuple must be (r,g,b) or (r,g,b,a); got $spec"))
    channel(x::Real) = UInt8(trunc(Int, x))
    rgb = (channel(spec[1]), channel(spec[2]), channel(spec[3]))
    return length(spec) == 3 ? (rgb..., 0xff) : (rgb..., channel(spec[4]))
end

parse_color(spec) = throw(ArgumentError("color must be a string or tuple, got $(typeof(spec))"))

"""Python `repr` for the values that appear in treescape error messages."""
pyrepr(s::AbstractString) = "'" * replace(s, "\\" => "\\\\", "'" => "\\'") * "'"
pyrepr(s::Symbol) = pyrepr(String(s))
pyrepr(v::AbstractVector) = "[" * join(map(pyrepr, v), ", ") * "]"
pyrepr(::Nothing) = "None"
pyrepr(x::AbstractFloat) = pyfloat(x)
pyrepr(x) = repr(x)

"""
    pyfloat(x) -> String

Format `x` like Python's `str(float(x))`: shortest round-trip digits,
fixed notation for decimal exponents in `(-4, 16]`, otherwise `1e-05` /
`1.5e+16` style. Used for the default scale-bar label.
"""
function pyfloat(x::Real)
    x = Float64(x)
    isnan(x) && return "nan"
    isinf(x) && return x > 0 ? "inf" : "-inf"
    x == 0 && return signbit(x) ? "-0.0" : "0.0"
    sign = x < 0 ? "-" : ""
    # Shortest round-trip digits from Julia's printer, re-laid-out.
    s = string(abs(x))
    mantissa, exp10 = occursin('e', s) ? (split(s, 'e')[1], parse(Int, split(s, 'e')[2])) : (s, 0)
    intpart, frac = occursin('.', mantissa) ? split(mantissa, '.') : (mantissa, "")
    digits = intpart * frac
    decpt = length(intpart) + exp10          # position of the decimal point
    lead = findfirst(!=('0'), digits)
    decpt -= lead - 1
    digits = rstrip(digits[lead:end], '0')
    if -4 < decpt <= 16
        body = if decpt <= 0
            "0." * "0"^(-decpt) * digits
        elseif decpt >= length(digits)
            digits * "0"^(decpt - length(digits)) * ".0"
        else
            digits[1:decpt] * "." * digits[(decpt + 1):end]
        end
        return sign * body
    end
    e = decpt - 1
    mant = length(digits) == 1 ? digits : digits[1:1] * "." * digits[2:end]
    return sign * mant * "e" * (e < 0 ? "-" : "+") * lpad(string(abs(e)), 2, '0')
end
