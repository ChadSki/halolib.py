# Copyright (c) 2013, Chad Zawistowski
# All rights reserved.
#
# This software is free and open source, released under the 2-clause BSD
# license as detailed in the LICENSE file.

import fnmatch
import os
import xml.etree.ElementTree as et
from observablefield import *
from Quickbeam.Low import ObservableDictionary


def observable_field_class(field_type, offset, length, reverse, maxlength, options, reflexive_class):
    """Return an object which reads/writes to a field of a plugin-defined struct.
    """
    # select and create the appropriate field type
    return {
        'int8': lambda: Int8Field(offset),
        'int16': lambda: Int16Field(offset),
        'int32': lambda: Int32Field(offset),
        'int64': lambda: Int64Field(offset),
        'uint8': lambda: UInt8Field(offset),
        'uint16': lambda: UInt16Field(offset),
        'uint32': lambda: UInt32Field(offset),
        'uint64': lambda: UInt64Field(offset),
        'float32': lambda: Float32Field(offset),
        'float64': lambda: Float64Field(offset),

        'colorbyte': lambda: ColorByteField(offset),
        'colorRGB': lambda: ColorRgbField(offset),
        'colorARGB': lambda: ColorArgbField(offset),

        'enum8': lambda: Enum8Field(offset, options),
        'enum16': lambda: Enum16Field(offset, options),
        'enum32': lambda: Enum32Field(offset, options),

        'bitmask8': lambda: Bitmask8Field(offset, options),
        'bitmask16': lambda: Bitmask16Field(offset, options),
        'bitmask32': lambda: Bitmask32Field(offset, options),

        'rawdata': lambda: RawDataField(offset, length),
        'ascii': lambda: AsciiField(offset, length, reverse),
        'asciiz': lambda: AsciizField(offset, maxlength),
        'stringptr': lambda: None,

        'loneID': lambda: ReferenceField(offset, False),
        'reference': lambda: ReferenceField(offset, True),
        'struct_array': lambda: StructArrayField(offset, struct_class)
    }[field_type]()


def struct_class_from_xml(layout):
    """Define a new class based on the given struct layout."""
    # Parse xml once ahead of time, rather than in the constructor
    field_classes = {
        field.attrib['name']: observable_field_class(
            field_type=field.tag,
            offset=int(field.attrib.get('offset'), 0),
            length=int(field.attrib.get('length', '0'), 0),
            reverse=field.attrib.get('reverse', 'false') == 'true',
            maxlength=int(field.attrib.get('maxlength', '0'), 0),
            options={
                opt.attrib['value']: opt.attrib['name'] for opt in field.iter('option')
            },
            reflexive_class=struct_class_from_xml(field) if field.tag == 'reflexive' else None,
        ) for field in layout
    }

    class HaloStruct(object):

        """Wraps an ObservableDictionary, presenting its fields as native Python properties."""

        # static variable, so ByteAccess objects know how large to be
        struct_size = int(layout.attrib['struct_size'], 0)

        def __init__(self, bytearray, halomap):
            object.__setattr__(self, 'bytearray', bytearray)
            object.__setattr__(self, 'halomap', halomap)

            # instantiate backing dictionary
            object.__setattr__(self, 'ObservableDictionary', ObservableDictionary[String, Object]())

            # fill with field fields
            for name in field_classes:
                field = field_classes[name](self)
                object.__getattribute__(self, 'ObservableDictionary')[name] = field

        def OnChanged(self, name):
            """Return the dictionary's OnChanged event."""
            return object.__getattribute__(self, 'ObservableDictionary')[name].OnChanged

        def __repr__(self):
            """Pseudo-JSON format."""
            answer = '{'
            for pair in self.__dict__:
                answer += '\n    %s: ' % pair.Key
                lines = str(pair.Value.Value).split('\n')
                answer += lines.pop(0)
                for line in lines:
                    answer += '\n    ' + line
                answer += ','
            answer += '\n}'
            return answer

        def __dir__(self):
            """Return names of the ObservableDictionary's fields."""
            return object.__getattribute__(self, 'ObservableDictionary').Keys

        def __getattribute__(self, name):
            """Redirect lookup to the ObservableDictionary's fields."""
            if name == 'bytearray':
                return object.__getattribute__(self, 'bytearray')

            elif name == 'halomap':
                return object.__getattribute__(self, 'halomap')

            elif name == '__dict__':
                # so C# can get the ObservableDictionary for databinding
                return object.__getattribute__(self, 'ObservableDictionary')

            elif name == 'OnChanged':
                return object.__getattribute__(self, 'OnChanged')

            else:
                # pass lookup through to the ObservableDictionary
                return object.__getattribute__(self, 'ObservableDictionary')[name].Value

        def __setattr__(self, name, value):
            """Redirect lookup to the ObservableDictionary's fields."""
            object.__getattribute__(self, 'ObservableDictionary')[name].Value = value

    return HaloStruct

plugin_classes = {}


def load_plugins():
    """Generate struct-wrapping classes based on xml plugins."""
    src_dir = os.path.dirname(os.path.abspath(__file__))
    plugins_dir = os.path.join(src_dir, 'plugins')
    for dirpath, dirnames, files in os.walk(plugins_dir):
        for filename in fnmatch.filter(files, '*.xml'):
            root_struct = et.parse(os.path.join(plugins_dir, filename)).getroot()  # load the xml definition
            plugin_classes[root_struct.attrib['name']] = struct_class_from_xml(root_struct)
