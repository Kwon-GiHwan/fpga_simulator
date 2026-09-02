#!/usr/bin/env python3
"""P0-C0 stage C0-4/C0-5 rewrite tool.

Inserts NPU_OP_IRQ command(s) into a compiled U85 Vela tflite at predeclared
boundaries, updating exactly: the cms bytes, the COMMAND_STREAM driver-action
length field, the cms tensor shape, and the containing flatbuffer.

Fail-closed: any schema feature outside the audited subset, any unknown
opcode/control word, and any post-write comparison difference beyond the
declared modification STOPs the run.

Usage:
  insert_irq.py <in.tflite> <out.tflite> --after-op NAME --count N [--param P]
  insert_irq.py <in.tflite> <out.tflite> --control          (unmodified copy)
"""
import argparse
import hashlib
import re
import sys

import flatbuffers
from ethosu.vela.tflite.Model import Model

HDR = "/opt/arm/ml-embedded-evaluation-kit/dependencies/core-driver/src/ethosu85_interface.h"
FOURCC = ord("1") << 24 | ord("P") << 16 | ord("O") << 8 | ord("C")


def die(msg):
    print("STOP:", msg)
    sys.exit(2)


def extract_enum(prefix):
    table = {}
    pat = re.compile(r"^\s*(%s[A-Z0-9_]+)\s*=\s*(\d+)\s*,?\s*$" % prefix)
    for line in open(HDR):
        m = pat.match(line)
        if m:
            table[int(m.group(2))] = m.group(1)
    if not table:
        die("no %s entries extracted from vendor header" % prefix)
    return table


CMD0 = extract_enum("CMD0_OPCODE_")
CMD1 = extract_enum("CMD1_OPCODE_")
IRQ_OPC = {v: k for k, v in CMD0.items()}["CMD0_OPCODE_NPU_OP_IRQ"]
OP_LAUNCH = {k for k in CMD0.values()
             if k.startswith("CMD0_OPCODE_NPU_OP_")
             and k not in ("CMD0_OPCODE_NPU_OP_STOP", "CMD0_OPCODE_NPU_OP_IRQ")
             and "DMA" not in k}


def decode_cms(cms):
    n = len(cms) // 4
    if len(cms) % 4:
        die("cms not word aligned")
    cmds, i = [], 0
    while i < n:
        w = int.from_bytes(cms[4 * i:4 * i + 4], "little")
        ctrl, opc, par = (w >> 14) & 3, w & 0x3FF, w >> 16
        if ctrl == 0:
            if opc not in CMD0:
                die("unknown CMD0 opcode %d" % opc)
            cmds.append((0, opc, par, None))
            i += 1
        elif ctrl == 1:
            if opc not in CMD1:
                die("unknown CMD1 opcode %d" % opc)
            if i + 1 >= n:
                die("truncated CMD1")
            cmds.append((1, opc, par, int.from_bytes(cms[4 * i + 4:4 * i + 8], "little")))
            i += 2
        else:
            die("reserved control %d" % ctrl)
    return cmds


def serialize_cms(cmds):
    out = bytearray()
    for ctrl, opc, par, pay in cmds:
        out += ((par << 16) | (ctrl << 14) | opc).to_bytes(4, "little")
        if ctrl == 1:
            out += pay.to_bytes(4, "little")
    return bytes(out)


def parse_payload(p):
    """Return (pre_words, cms, post_words) where pre/post are raw byte spans
    around the single COMMAND_STREAM action's cms."""
    if len(p) % 4:
        die("payload not word aligned")
    if int.from_bytes(p[0:4], "little") != FOURCC:
        die("payload fourcc mismatch")
    words = len(p) // 4
    i = 1
    while i < words:
        w = int.from_bytes(p[4 * i:4 * i + 4], "little")
        cmd = w & 0xFF
        if cmd == 1:
            i += 3
        elif cmd == 2:
            ln = ((w >> 8) & 0xFF) << 16 | (w >> 16)
            pre = p[:4 * i]           # up to and excluding the CS action word
            cms = p[4 * (i + 1):4 * (i + 1 + ln)]
            post = p[4 * (i + 1 + ln):]
            if len(cms) != 4 * ln:
                die("cms extends past payload")
            return pre, w, cms, post
        elif cmd == 5:
            i += 1
        else:
            die("unknown driver_action %d" % cmd)
    die("no COMMAND_STREAM action found")


def rebuild_payload(pre, cms, post):
    ln = len(cms) // 4
    if ln >= (1 << 24):
        die("cms length exceeds 24-bit field")
    action = (2) | ((ln >> 16) & 0xFF) << 8 | (ln & 0xFFFF) << 16
    return pre + action.to_bytes(4, "little") + cms + post


# ---------------- deep-copy flatbuffer writer (audited subset only) ------

def guard(cond, msg):
    if not cond:
        die("unsupported schema feature: " + msg)


def copy_model(src_bytes, replace_cms=None):
    """Deep-copy the tflite; replace_cms = (buffer_index, new_bytes,
    cms_tensor_index) or None for a control copy."""
    m = Model.GetRootAsModel(src_bytes, 0)
    guard(m.SubgraphsLength() == 1, "multiple subgraphs")
    guard(getattr(m, "SignatureDefsLength", lambda: 0)() == 0, "signature_defs")
    sg = m.Subgraphs(0)

    b = flatbuffers.Builder(len(src_bytes) + 256)

    # buffers
    buf_offs = []
    for i in range(m.BuffersLength()):
        bu = m.Buffers(i)
        if replace_cms and i == replace_cms[0]:
            data = replace_cms[1]
        elif bu.DataLength():
            data = bu.DataAsNumpy().tobytes()
        else:
            data = None
        from ethosu.vela.tflite import Buffer
        if data is not None:
            # tflite schema: Buffer.data has force_align: 16. The runtime
            # driver enforces 16-byte alignment on cms and base addresses.
            # Emulate C++ ForceVectorAlignment(len,1,16): pad so the vector
            # DATA (not its length prefix) starts 16-aligned, and raise
            # minalign so Finish preserves absolute alignment. Verified by
            # check_alignment() on every output.
            b.Prep(16, len(data))
            dv = b.CreateByteVector(data)
            Buffer.BufferStart(b)
            Buffer.BufferAddData(b, dv)
        else:
            Buffer.BufferStart(b)
        buf_offs.append(Buffer.BufferEnd(b))

    # operator codes
    from ethosu.vela.tflite import OperatorCode
    oc_offs = []
    for i in range(m.OperatorCodesLength()):
        oc = m.OperatorCodes(i)
        cc = oc.CustomCode()
        cc_off = b.CreateString(cc) if cc else None
        OperatorCode.OperatorCodeStart(b)
        OperatorCode.OperatorCodeAddDeprecatedBuiltinCode(b, oc.DeprecatedBuiltinCode())
        if cc_off:
            OperatorCode.OperatorCodeAddCustomCode(b, cc_off)
        OperatorCode.OperatorCodeAddVersion(b, oc.Version())
        OperatorCode.OperatorCodeAddBuiltinCode(b, oc.BuiltinCode())
        oc_offs.append(OperatorCode.OperatorCodeEnd(b))

    # tensors
    from ethosu.vela.tflite import Tensor, QuantizationParameters
    t_offs = []
    for i in range(sg.TensorsLength()):
        t = sg.Tensors(i)
        guard(t.Sparsity() is None, "sparsity")
        guard(t.ShapeSignatureLength() == 0, "shape_signature")
        guard(not t.IsVariable(), "variable tensor")
        q = t.Quantization()
        q_off = None
        if q is not None:
            guard(q.DetailsType() == 0, "quantization details")
            def fvec(n, get, make):
                if n == 0:
                    return None
                vals = [get(j) for j in range(n)]
                make(b, n)
                for v in reversed(vals):
                    (b.PrependFloat32 if isinstance(v, float) else b.PrependInt64)(v)
                return b.EndVector()
            mn = fvec(q.MinLength(), q.Min, QuantizationParameters.QuantizationParametersStartMinVector)
            mx = fvec(q.MaxLength(), q.Max, QuantizationParameters.QuantizationParametersStartMaxVector)
            sc = fvec(q.ScaleLength(), q.Scale, QuantizationParameters.QuantizationParametersStartScaleVector)
            zp = fvec(q.ZeroPointLength(), lambda j: int(q.ZeroPoint(j)),
                      QuantizationParameters.QuantizationParametersStartZeroPointVector)
            QuantizationParameters.QuantizationParametersStart(b)
            if mn: QuantizationParameters.QuantizationParametersAddMin(b, mn)
            if mx: QuantizationParameters.QuantizationParametersAddMax(b, mx)
            if sc: QuantizationParameters.QuantizationParametersAddScale(b, sc)
            if zp: QuantizationParameters.QuantizationParametersAddZeroPoint(b, zp)
            QuantizationParameters.QuantizationParametersAddQuantizedDimension(b, q.QuantizedDimension())
            q_off = QuantizationParameters.QuantizationParametersEnd(b)
        shape = [t.Shape(j) for j in range(t.ShapeLength())]
        if replace_cms and i == replace_cms[2]:
            guard(shape == [len(src_cms_bytes_holder[0])], "cms tensor shape != payload bytes")
            shape = [len(replace_cms[1])]
        name_off = b.CreateString(t.Name())
        Tensor.TensorStartShapeVector(b, len(shape))
        for v in reversed(shape):
            b.PrependInt32(v)
        sh_off = b.EndVector()
        Tensor.TensorStart(b)
        Tensor.TensorAddShape(b, sh_off)
        Tensor.TensorAddType(b, t.Type())
        Tensor.TensorAddBuffer(b, t.Buffer())
        Tensor.TensorAddName(b, name_off)
        if q_off:
            Tensor.TensorAddQuantization(b, q_off)
        t_offs.append(Tensor.TensorEnd(b))

    # operators
    from ethosu.vela.tflite import Operator, SubGraph, Metadata
    op_offs = []
    for i in range(sg.OperatorsLength()):
        op = sg.Operators(i)
        guard(op.BuiltinOptionsType() == 0, "builtin options on op %d" % i)
        guard(op.MutatingVariableInputsLength() == 0, "mutating_variable_inputs")
        guard(getattr(op, "IntermediatesLength", lambda: 0)() == 0, "intermediates")
        co = bytes(op.CustomOptionsAsNumpy().tobytes()) if op.CustomOptionsLength() else None
        co_off = b.CreateByteVector(co) if co else None
        ins = [op.Inputs(j) for j in range(op.InputsLength())]
        outs = [op.Outputs(j) for j in range(op.OutputsLength())]
        Operator.OperatorStartInputsVector(b, len(ins))
        for v in reversed(ins):
            b.PrependInt32(v)
        in_off = b.EndVector()
        Operator.OperatorStartOutputsVector(b, len(outs))
        for v in reversed(outs):
            b.PrependInt32(v)
        out_off = b.EndVector()
        Operator.OperatorStart(b)
        Operator.OperatorAddOpcodeIndex(b, op.OpcodeIndex())
        Operator.OperatorAddInputs(b, in_off)
        Operator.OperatorAddOutputs(b, out_off)
        if co_off:
            Operator.OperatorAddCustomOptions(b, co_off)
            Operator.OperatorAddCustomOptionsFormat(b, op.CustomOptionsFormat())
        op_offs.append(Operator.OperatorEnd(b))

    sg_in = [sg.Inputs(j) for j in range(sg.InputsLength())]
    sg_out = [sg.Outputs(j) for j in range(sg.OutputsLength())]
    sg_name = b.CreateString(sg.Name()) if sg.Name() else None
    SubGraph.SubGraphStartTensorsVector(b, len(t_offs))
    for v in reversed(t_offs):
        b.PrependUOffsetTRelative(v)
    tv = b.EndVector()
    SubGraph.SubGraphStartInputsVector(b, len(sg_in))
    for v in reversed(sg_in):
        b.PrependInt32(v)
    iv = b.EndVector()
    SubGraph.SubGraphStartOutputsVector(b, len(sg_out))
    for v in reversed(sg_out):
        b.PrependInt32(v)
    ov = b.EndVector()
    SubGraph.SubGraphStartOperatorsVector(b, len(op_offs))
    for v in reversed(op_offs):
        b.PrependUOffsetTRelative(v)
    opv = b.EndVector()
    SubGraph.SubGraphStart(b)
    SubGraph.SubGraphAddTensors(b, tv)
    SubGraph.SubGraphAddInputs(b, iv)
    SubGraph.SubGraphAddOutputs(b, ov)
    SubGraph.SubGraphAddOperators(b, opv)
    if sg_name:
        SubGraph.SubGraphAddName(b, sg_name)
    sg_off = SubGraph.SubGraphEnd(b)

    md_offs = []
    for i in range(m.MetadataLength()):
        md = m.Metadata(i)
        nm = b.CreateString(md.Name())
        Metadata.MetadataStart(b)
        Metadata.MetadataAddName(b, nm)
        Metadata.MetadataAddBuffer(b, md.Buffer())
        md_offs.append(Metadata.MetadataEnd(b))

    from ethosu.vela.tflite import Model as ModelMod
    desc = b.CreateString(m.Description()) if m.Description() else None
    ModelMod.ModelStartOperatorCodesVector(b, len(oc_offs))
    for v in reversed(oc_offs):
        b.PrependUOffsetTRelative(v)
    ocv = b.EndVector()
    ModelMod.ModelStartSubgraphsVector(b, 1)
    b.PrependUOffsetTRelative(sg_off)
    sgv = b.EndVector()
    ModelMod.ModelStartBuffersVector(b, len(buf_offs))
    for v in reversed(buf_offs):
        b.PrependUOffsetTRelative(v)
    bv = b.EndVector()
    mdv = None
    if md_offs:
        ModelMod.ModelStartMetadataVector(b, len(md_offs))
        for v in reversed(md_offs):
            b.PrependUOffsetTRelative(v)
        mdv = b.EndVector()
    ModelMod.ModelStart(b)
    ModelMod.ModelAddVersion(b, m.Version())
    ModelMod.ModelAddOperatorCodes(b, ocv)
    ModelMod.ModelAddSubgraphs(b, sgv)
    if desc:
        ModelMod.ModelAddDescription(b, desc)
    ModelMod.ModelAddBuffers(b, bv)
    if mdv:
        ModelMod.ModelAddMetadata(b, mdv)
    root = ModelMod.ModelEnd(b)
    b.Finish(root, file_identifier=b"TFL3")
    return bytes(b.Output())


# ---------------- verification comparator --------------------------------

def compare(orig, new, allow_cms=None):
    """allow_cms = (buffer_index, cms_tensor_index) whose difference is the
    declared modification; everything else must match exactly."""
    a, c = Model.GetRootAsModel(orig, 0), Model.GetRootAsModel(new, 0)
    assert a.Version() == c.Version()
    assert a.Description() == c.Description()
    assert a.OperatorCodesLength() == c.OperatorCodesLength()
    for i in range(a.OperatorCodesLength()):
        x, y = a.OperatorCodes(i), c.OperatorCodes(i)
        assert (x.DeprecatedBuiltinCode(), x.CustomCode(), x.Version(), x.BuiltinCode()) == \
               (y.DeprecatedBuiltinCode(), y.CustomCode(), y.Version(), y.BuiltinCode())
    assert a.BuffersLength() == c.BuffersLength()
    diff_bufs = []
    for i in range(a.BuffersLength()):
        da = a.Buffers(i).DataAsNumpy().tobytes() if a.Buffers(i).DataLength() else b""
        dc = c.Buffers(i).DataAsNumpy().tobytes() if c.Buffers(i).DataLength() else b""
        if da != dc:
            diff_bufs.append(i)
    assert a.MetadataLength() == c.MetadataLength()
    for i in range(a.MetadataLength()):
        assert (a.Metadata(i).Name(), a.Metadata(i).Buffer()) == \
               (c.Metadata(i).Name(), c.Metadata(i).Buffer())
    sa, sc = a.Subgraphs(0), c.Subgraphs(0)
    assert sa.TensorsLength() == sc.TensorsLength()
    diff_tensors = []
    for i in range(sa.TensorsLength()):
        x, y = sa.Tensors(i), sc.Tensors(i)
        fx = (x.Name(), x.Type(), x.Buffer(), [x.Shape(j) for j in range(x.ShapeLength())])
        fy = (y.Name(), y.Type(), y.Buffer(), [y.Shape(j) for j in range(y.ShapeLength())])
        if fx != fy:
            diff_tensors.append(i)
        qx, qy = x.Quantization(), y.Quantization()
        assert (qx is None) == (qy is None)
        if qx is not None:
            assert [qx.Scale(j) for j in range(qx.ScaleLength())] == [qy.Scale(j) for j in range(qy.ScaleLength())]
            assert [int(qx.ZeroPoint(j)) for j in range(qx.ZeroPointLength())] == \
                   [int(qy.ZeroPoint(j)) for j in range(qy.ZeroPointLength())]
    assert [sa.Inputs(j) for j in range(sa.InputsLength())] == [sc.Inputs(j) for j in range(sc.InputsLength())]
    assert [sa.Outputs(j) for j in range(sa.OutputsLength())] == [sc.Outputs(j) for j in range(sc.OutputsLength())]
    assert sa.OperatorsLength() == sc.OperatorsLength()
    for i in range(sa.OperatorsLength()):
        x, y = sa.Operators(i), sc.Operators(i)
        assert x.OpcodeIndex() == y.OpcodeIndex()
        assert [x.Inputs(j) for j in range(x.InputsLength())] == [y.Inputs(j) for j in range(y.InputsLength())]
        assert [x.Outputs(j) for j in range(x.OutputsLength())] == [y.Outputs(j) for j in range(y.OutputsLength())]
        xa = x.CustomOptionsAsNumpy().tobytes() if x.CustomOptionsLength() else b""
        ya = y.CustomOptionsAsNumpy().tobytes() if y.CustomOptionsLength() else b""
        assert xa == ya
    if allow_cms is None:
        assert diff_bufs == [] and diff_tensors == [], (diff_bufs, diff_tensors)
    else:
        assert diff_bufs == [allow_cms[0]], diff_bufs
        assert diff_tensors == [allow_cms[1]], diff_tensors
    return True


# ---------------- main ---------------------------------------------------

src_cms_bytes_holder = [b""]
src_extra_holder = [0]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--after-op", default="CMD0_OPCODE_NPU_OP_CONV")
    ap.add_argument("--count", type=int, default=0, help="number of IRQs; 0 = control copy")
    ap.add_argument("--param", type=int, default=1)
    a = ap.parse_args()

    src = open(a.src, "rb").read()
    m = Model.GetRootAsModel(src, 0)
    sg = m.Subgraphs(0)
    cms_ti = cms_bi = None
    for i in range(sg.OperatorsLength()):
        oc = m.OperatorCodes(sg.Operators(i).OpcodeIndex())
        if oc.CustomCode() and b"ethos-u" in oc.CustomCode().lower():
            cms_ti = sg.Operators(i).Inputs(0)
            cms_bi = sg.Tensors(cms_ti).Buffer()
    if cms_ti is None:
        die("no ethos-u custom op found")
    payload = m.Buffers(cms_bi).DataAsNumpy().tobytes()
    src_cms_bytes_holder[0] = payload
    pre, action, cms, post = parse_payload(payload)
    cmds = decode_cms(cms)
    if serialize_cms(cmds) != cms:
        die("SERIALIZER_NOT_IDENTITY_PRESERVING on input")

    def check_alignment(model_bytes):
        mm = Model.GetRootAsModel(model_bytes, 0)
        for bi in range(mm.BuffersLength()):
            bu = mm.Buffers(bi)
            off = bu._tab.Offset(4)
            if off and bu._tab.Vector(off) % 16:
                die("buffer %d data misaligned (%d)" % (bi, bu._tab.Vector(off) % 16))

    if a.count == 0:
        out = copy_model(src, None)
        compare(src, out, None)
        check_alignment(out)
        mode = "CONTROL"
    else:
        launches = [i for i, (ctrl, opc, _, _) in enumerate(cmds)
                    if ctrl == 0 and CMD0[opc] == a.after_op]
        if len(launches) < a.count:
            die("only %d %s launches; need %d" % (len(launches), a.after_op, a.count))
        newc = list(cmds)
        for k, li in enumerate(sorted(launches[:a.count], reverse=True)):
            newc.insert(li + 1, (0, IRQ_OPC, a.param + (a.count - 1 - k), None))
        new_cms = serialize_cms(newc)
        assert len(new_cms) == len(cms) + 4 * a.count
        new_payload = rebuild_payload(pre, new_cms, post)
        src_extra_holder[0] = len(new_payload) - len(payload)
        out = copy_model(src, (cms_bi, new_payload, cms_ti))
        compare(src, out, (cms_bi, cms_ti))
        check_alignment(out)
        # decoded modified stream must equal original + the inserted IRQs
        m2 = Model.GetRootAsModel(out, 0)
        p2 = m2.Buffers(cms_bi).DataAsNumpy().tobytes()
        _, _, cms2, _ = parse_payload(p2)
        c2 = decode_cms(cms2)
        stripped = [c for c in c2 if not (c[0] == 0 and c[1] == IRQ_OPC)]
        assert stripped == cmds, "modified stream differs beyond inserted IRQs"
        assert len(c2) - len(stripped) == a.count
        mode = "IRQx%d after %s" % (a.count, a.after_op)

    open(a.dst, "wb").write(out)
    h = lambda x: hashlib.sha256(x).hexdigest()
    print("MODE:", mode)
    print("src_tflite_sha256:", h(src))
    print("dst_tflite_sha256:", h(out))
    print("orig_cms_sha256:", h(cms))
    if a.count:
        print("mod_cms_sha256:", h(new_cms))
    print("VERIFY: PASS")


if __name__ == "__main__":
    main()
