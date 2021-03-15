#!/usr/bin/env python3
import sys
import io
import subprocess
import re

from cmsis_svd.parser import SVDParser

def cleanup_description(description):
    if description is None:
        return ''

    return ' '.join(description.replace('\n', ' ').split())

# register names in from Nordic SVDs are using foo[n] for couple of registers
# and also for somereaons there are %s in the reigster names
name_regex = re.compile(r"\[([^\]]+)]")
def cleanup_name(name):
    return name_regex.sub(r"_\1", name).replace("%", "_")

class MMIOFileGenerator:
    def __init__(self, f):
        self.f = f

    def generate_padding(self, count):
        if count > 0:
            self.write_line(f"padding: u{count} = 0,")

    def generate_reserved(self, count, field):
        self.write_line(f"reserved{field}: u{count} = 0,")

    def generate_register_field(self, field):
        '''
        returns something like:
            name: u<size>, // bit offset: 0 desc: foo description
        '''
        field.description = cleanup_description(field.description)
        field_type = f"u{field.bit_width}" if field.bit_width != 1 else 'bool'
        self.write_line(f"{field.name}:{field_type},// bit offset: {field.bit_offset} desc: {field.description}")
        return field.bit_offset + field.bit_width

    def generate_register_declaration(self, register):
        '''

        '''
        register.description = cleanup_description(register.description)
        self.write_line(f"// byte offset: {register.address_offset} {register.description}")
        register.name = cleanup_name(register.name)
        self.write_line(f" pub const {register.name} = MMIO(Address + 0x{register.address_offset:08x}, u{register.size}, packed struct{{")
        last_offset = 0
        reserved_index = 0
        for field in sorted(register.fields, key=lambda f: f.bit_offset):
            if last_offset != field.bit_offset:
                self.generate_reserved(field.bit_offset - last_offset, reserved_index)
                reserved_index = reserved_index + 1

            last_offset = self.generate_register_field(field)

        if register.size is not None:
            self.generate_padding(register.size - last_offset)

        self.write_line("});")

    def generate_peripherial_declaration(self, peripherial):
        self.write_line(f"pub const {peripherial.name} = extern struct {{")
        self.write_line(f"pub const Address: u32 = 0x{peripherial.base_address:08x};")

        for register in sorted(peripherial.registers, key=lambda f: f.address_offset):
            self.generate_register_declaration(register)

        self.write_line("};")

    def generate_file(self, device):
        self.write_line("// generated using gen_zig_from_svd.py\n// DO NOT EDIT")
        self.write_line(f"// based on {device.name} version {device.version}")

        self.write_line("const MMIO = @import(\"../../common/mmio.zig\").MMIO;")
        self.write_line(f"const Name = \"{device.name}\";")
        for peripherial in device.peripherals:
            self.generate_peripherial_declaration(peripherial)

    def write_line(self, line):
        self.f.write(line + "\n")



def main():
    parser = SVDParser.for_packaged_svd(sys.argv[1], sys.argv[2] + '.svd')
    device = parser.get_device()

    zig_fmt = subprocess.Popen(('zig', 'fmt', '--stdin'), stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, encoding='utf8')

    generator = MMIOFileGenerator(zig_fmt.stdin)
    generator.generate_file(device)

    zig_fmt.stdin.flush()
    zig_fmt.stdin.close()
    print(zig_fmt.stdout.read())


if __name__ == "__main__":
    main()
