"""Kraken - objects.Controls.NullControl module.

Classes:
BaseControl - Base Control.

"""

from kraken.core.maths import Vec3
from kraken.core.objects.controls.base_control import BaseControl


class NullControl(BaseControl):
    """Square Control object."""

    def __init__(self, name, parent=None):
        """Initializes base control object.

        Arguments:
        name -- String, Name of the constraint.
        parent -- Object, parent object of this object.

        """

        super(NullControl, self).__init__(name, parent=parent)
        self.addCurveSection([Vec3(1, 0, -1), Vec3(1, 0, 1), Vec3(-1, 0, 1), Vec3(-1, 0, -1)], True)