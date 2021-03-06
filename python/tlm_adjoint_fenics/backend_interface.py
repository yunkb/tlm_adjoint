#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# For tlm_adjoint copyright information see ACKNOWLEDGEMENTS in the tlm_adjoint
# root directory

# This file is part of tlm_adjoint.
#
# tlm_adjoint is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# tlm_adjoint is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with tlm_adjoint.  If not, see <https://www.gnu.org/licenses/>.

from .backend import *
from .backend_code_generator_interface import assemble, \
    copy_parameters_dict, r0_space
from .interface import *
from .interface import FunctionInterface as _FunctionInterface

from .caches import clear_caches, form_neg
from .functions import Caches, Constant, Function, Replacement, Zero, \
    is_r0_function

import mpi4py.MPI as MPI
import numpy as np
import ufl
import warnings

__all__ = \
    [
        "InterfaceException",

        "is_space",
        "space_comm",
        "space_id",
        "space_new",

        "is_function",
        "function_assign",
        "function_axpy",
        "function_caches",
        "function_comm",
        "function_copy",
        "function_get_values",
        "function_global_size",
        "function_id",
        "function_inner",
        "function_is_cached",
        "function_is_checkpointed",
        "function_is_static",
        "function_linf_norm",
        "function_local_indices",
        "function_local_size",
        "function_max_value",
        "function_name",
        "function_new",
        "function_replacement",
        "function_set_values",
        "function_space",
        "function_state",
        "function_sum",
        "function_tangent_linear",
        "function_update_caches",
        "function_update_state",
        "function_zero",

        "is_real_function",
        "new_real_function",
        "real_function_value",

        "clear_caches",
        "copy_parameters_dict",
        "default_comm",
        "finalize_adjoint_derivative_action",
        "info",
        "subtract_adjoint_derivative_action",

        "Constant",
        "Function",
        "Replacement",

        "RealFunctionSpace",
        "function_space_id",
        "function_space_new",
        "warning"
    ]


def default_comm():
    return MPI.COMM_WORLD


class FunctionSpaceInterface(SpaceInterface):
    def _comm(self):
        return self.mesh().mpi_comm()

    def _id(self):
        return self.id()

    def _new(self, name=None, static=False, cache=None, checkpoint=None):
        return Function(self, name=name, static=static, cache=cache,
                        checkpoint=checkpoint)


def _FunctionSpace__init__(self, *args, **kwargs):
    backend_FunctionSpace._tlm_adjoint__orig___init__(self, *args, **kwargs)
    add_interface(self, FunctionSpaceInterface)


backend_FunctionSpace._tlm_adjoint__orig___init__ = backend_FunctionSpace.__init__  # noqa: E501
backend_FunctionSpace.__init__ = _FunctionSpace__init__


class FunctionInterface(_FunctionInterface):
    def _comm(self):
        return self.function_space().mesh().mpi_comm()

    def _space(self):
        return self.function_space()

    def _id(self):
        return self.id()

    def _name(self):
        return self.name()

    def _state(self):
        if not hasattr(self, "_tlm_adjoint__state"):
            self._tlm_adjoint__state = 0
        return self._tlm_adjoint__state

    def _update_state(self):
        if hasattr(self, "_tlm_adjoint__state"):
            self._tlm_adjoint__state += 1
        else:
            self._tlm_adjoint__state = 1

    def _is_static(self):
        if hasattr(self, "is_static"):
            return self.is_static()
        else:
            return False

    def _is_cached(self):
        if hasattr(self, "is_cached"):
            return self.is_cached()
        else:
            return False

    def _is_checkpointed(self):
        if hasattr(self, "is_checkpointed"):
            return self.is_checkpointed()
        else:
            return True

    def _caches(self):
        if not hasattr(self, "_tlm_adjoint__caches"):
            self._tlm_adjoint__caches = Caches(self)
        return self._tlm_adjoint__caches

    def _update_caches(self, value=None):
        if value is None:
            value = self
        function_caches(self).update(value)

    def _zero(self):
        self.vector().zero()

    def _assign(self, y):
        if isinstance(y, backend_Function):
            if self.vector().local_size() != y.vector().local_size():
                raise InterfaceException("Invalid function space")
            self.vector().zero()
            self.vector().axpy(1.0, y.vector())
        elif isinstance(y, (int, float)):
            if len(self.ufl_shape) == 0:
                self.assign(backend_Constant(float(y)),
                            annotate=False, tlm=False)
            else:
                y_ = np.full(self.ufl_shape, float(y), dtype=np.float64)
                self.assign(backend_Constant(y_),
                            annotate=False, tlm=False)
        elif isinstance(y, Zero):
            self.vector().zero()
        else:
            assert isinstance(y, backend_Constant)
            self.assign(y, annotate=False, tlm=False)

    def _axpy(self, *args):  # self, alpha, x
        alpha, x = args
        if isinstance(x, backend_Function):
            if self.vector().local_size() != x.vector().local_size():
                raise InterfaceException("Invalid function space")
            self.vector().axpy(alpha, x.vector())
        elif isinstance(x, Zero):
            pass
        else:
            assert isinstance(x, backend_Constant)
            if is_r0_function(self):
                self.assign(backend_Constant(self.vector().max()
                                             + alpha * float(x)),
                            annotate=False, tlm=False)
            else:
                x_ = backend_Function(self.function_space())
                x_.assign(x, annotate=False, tlm=False)
                self.vector().axpy(alpha, x_.vector())

    def _inner(self, y):
        if isinstance(y, backend_Function):
            if self.vector().local_size() != y.vector().local_size():
                raise InterfaceException("Invalid function space")
            return self.vector().inner(y.vector())
        elif isinstance(y, Zero):
            return 0.0
        else:
            assert isinstance(y, backend_Constant)
            if len(y.ufl_shape) == 0:
                return self.vector().sum() * float(y)
            else:
                y_ = backend_Function(self.function_space())
                y_.assign(y, annotate=False, tlm=False)
                return self.vector().inner(y_.vector())

    def _max_value(self):
        return self.vector().max()

    def _sum(self):
        return self.vector().sum()

    def _linf_norm(self):
        return self.vector().norm("linf")

    def _local_size(self):
        return self.vector().local_size()

    def _global_size(self):
        return self.function_space().dofmap().global_dimension()

    def _local_indices(self):
        return slice(*self.function_space().dofmap().ownership_range())

    def _get_values(self):
        values = self.vector().get_local().view()
        values.setflags(write=False)
        if not np.can_cast(values, np.float64):
            raise InterfaceException("Invalid dtype")
        return values

    def _set_values(self, values):
        if not np.can_cast(values, backend_ScalarType):
            raise InterfaceException("Invalid dtype")
        if values.shape != (self.vector().local_size(),):
            raise InterfaceException("Invalid shape")
        self.vector().set_local(values)
        self.vector().apply("insert")

    def _new(self, name=None, static=False, cache=None, checkpoint=None):
        y = function_copy(self, name=name, static=static, cache=cache,
                          checkpoint=checkpoint)
        y.vector().zero()
        return y

    def _copy(self, name=None, static=False, cache=None, checkpoint=None):
        y = self.copy(deepcopy=True)
        if name is not None:
            y.rename(name, "a Function")
        y.is_static = lambda: static
        if cache is None:
            cache = static
        y.is_cached = lambda: cache
        if checkpoint is None:
            checkpoint = not static
        y.is_checkpointed = lambda: checkpoint
        return y

    def _tangent_linear(self, name=None):
        if hasattr(self, "tangent_linear"):
            return self.tangent_linear(name=name)
        elif function_is_static(self):
            return None
        else:
            return function_new(self, name=name, static=False,
                                cache=function_is_cached(self),
                                checkpoint=function_is_checkpointed(self))

    def _replacement(self):
        if not hasattr(self, "_tlm_adjoint__replacement"):
            self._tlm_adjoint__replacement = Replacement(self)
        return self._tlm_adjoint__replacement


def _Function__init__(self, *args, **kwargs):
    backend_Function._tlm_adjoint__orig___init__(self, *args, **kwargs)
    add_interface(self, FunctionInterface)


backend_Function._tlm_adjoint__orig___init__ = backend_Function.__init__
backend_Function.__init__ = _Function__init__


def is_real_function(x):
    return is_r0_function(x) and len(x.ufl_shape) == 0


def new_real_function(name=None, domain=None, comm=None, static=False,
                      cache=None, checkpoint=None):
    return Constant(0.0, name=name, domain=domain, comm=comm, static=static,
                    cache=cache, checkpoint=checkpoint)


def real_function_value(x):
    assert is_real_function(x)
    return function_max_value(x)


# def clear_caches(*deps):


# def info(message):


# def copy_parameters_dict(parameters):


def subtract_adjoint_derivative_action(x, y):
    if y is None:
        pass
    elif isinstance(y, ufl.classes.Form):
        if hasattr(x, "_tlm_adjoint__adj_b"):
            x._tlm_adjoint__adj_b += form_neg(y)
        else:
            x._tlm_adjoint__adj_b = form_neg(y)
    else:
        if isinstance(y, tuple):
            alpha, y = y
        else:
            alpha = 1.0
        if isinstance(y, backend_Vector):
            if isinstance(x, backend_Constant):
                if len(x.ufl_shape) == 0:
                    # annotate=False, tlm=False
                    x.assign(float(x) - alpha * y.max())
                else:
                    y_fn = Function(r0_space(x))

                    # Ordering check
                    check_values = np.arange(np.prod(x.ufl_shape),
                                             dtype=np.float64)
                    # annotate=False, tlm=False
                    y_fn.assign(backend_Constant(check_values.reshape(x.ufl_shape)))  # noqa: E501
                    for i, y_fn_c in enumerate(y_fn.split(deepcopy=True)):
                        assert y_fn_c.vector().max() == check_values[i]
                    y_fn.vector().zero()

                    value = x.values()
                    y_fn.vector().axpy(1.0, y)
                    for i, y_fn_c in enumerate(y_fn.split(deepcopy=True)):
                        value[i] -= alpha * y_fn_c.vector().max()
                    value.shape = x.ufl_shape
                    # annotate=False, tlm=False
                    x.assign(backend_Constant(value))
            else:
                if x.vector().local_size() != y.local_size():
                    raise InterfaceException("Invalid function space")
                x.vector().axpy(-alpha, y)
        else:
            function_axpy(x, -alpha, y)


def finalize_adjoint_derivative_action(x):
    if hasattr(x, "_tlm_adjoint__adj_b"):
        if isinstance(x, backend_Constant):
            y = assemble(x._tlm_adjoint__adj_b)
            subtract_adjoint_derivative_action(x, (-1.0, y))
        else:
            assemble(x._tlm_adjoint__adj_b, tensor=x.vector(),
                     add_values=True)
        delattr(x, "_tlm_adjoint__adj_b")


def RealFunctionSpace(comm=MPI.COMM_WORLD):
    warnings.warn("RealFunctionSpace is deprecated -- "
                  "use new_real_function instead",
                  DeprecationWarning, stacklevel=2)
    return FunctionSpace(UnitIntervalMesh(comm, comm.size), "R", 0)


def function_space_id(*args, **kwargs):
    warnings.warn("function_space_id is deprecated -- use space_id instead",
                  DeprecationWarning, stacklevel=2)
    return space_id(*args, **kwargs)


def function_space_new(*args, **kwargs):
    warnings.warn("function_space_new is deprecated -- use space_new instead",
                  DeprecationWarning, stacklevel=2)
    return space_new(*args, **kwargs)


def warning(message):
    warnings.warn("warning is deprecated -- use warnings.warn instead",
                  DeprecationWarning, stacklevel=2)
    warnings.warn(message, RuntimeWarning)
