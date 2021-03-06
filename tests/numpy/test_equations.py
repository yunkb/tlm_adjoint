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

from tlm_adjoint_numpy import *

from test_base import *

import numpy as np
import pytest


@pytest.mark.numpy
def test_AssignmentSolver(setup_test, test_leaks):
    x = Constant(16.0, name="x", static=True)

    def forward(x):
        y = [Constant(name=f"y_{i:d}") for i in range(9)]
        z = Constant(name="z")

        AssignmentSolver(x, y[0]).solve()
        for i in range(len(y) - 1):
            AssignmentSolver(y[i], y[i + 1]).solve()
        NormSqSolver(y[-1], z).solve()

        x_norm_sq = Constant(name="x_norm_sq")
        NormSqSolver(x, x_norm_sq).solve()

        z_norm_sq = Constant(name="z_norm_sq")
        NormSqSolver(z, z_norm_sq).solve()

        J = Functional(name="J")
        AxpySolver(z_norm_sq, 2.0, x_norm_sq, J.fn()).solve()

        K = Functional(name="K")
        AssignmentSolver(z_norm_sq, K.fn()).solve()

        return J, K

    start_manager()
    J, K = forward(x)
    stop_manager()

    assert abs(J.value() - 66048.0) == 0.0
    assert abs(K.value() - 65536.0) == 0.0

    dJs = compute_gradient([J, K], x)

    dm = Constant(1.0, name="dm", static=True)

    for forward_J, J_val, dJ in [(lambda x: forward(x)[0], J.value(), dJs[0]),
                                 (lambda x: forward(x)[1], K.value(), dJs[1])]:
        min_order = taylor_test(forward_J, x, J_val=J_val, dJ=dJ, dM=dm)
        assert min_order > 2.00

        ddJ = Hessian(forward_J)
        min_order = taylor_test(forward_J, x, J_val=J_val, ddJ=ddJ, dM=dm)
        assert min_order > 3.00

        min_order = taylor_test_tlm(forward_J, x, tlm_order=1, dMs=(dm,))
        assert min_order > 2.00

        min_order = taylor_test_tlm_adjoint(forward_J, x, adjoint_order=1,
                                            dMs=(dm,))
        assert min_order > 2.00

        min_order = taylor_test_tlm_adjoint(forward_J, x, adjoint_order=2,
                                            dMs=(dm, dm))
        assert min_order > 2.00


@pytest.mark.numpy
def test_AxpySolver(setup_test, test_leaks):
    x = Constant(1.0, name="x", static=True)

    def forward(x):
        y = [Constant(name=f"y_{i:d}") for i in range(5)]
        z = [Constant(name=f"z_{i:d}") for i in range(2)]
        z[0].assign(7.0)

        AssignmentSolver(x, y[0]).solve()
        for i in range(len(y) - 1):
            AxpySolver(y[i], i + 1, z[0], y[i + 1]).solve()
        NormSqSolver(y[-1], z[1]).solve()

        J = Functional(name="J")
        NormSqSolver(z[1], J.fn()).solve()
        return J

    start_manager()
    J = forward(x)
    stop_manager()

    J_val = J.value()
    assert abs(J_val - 25411681.0) == 0.0

    dJ = compute_gradient(J, x)

    dm = Constant(1.0, name="dm", static=True)

    min_order = taylor_test(forward, x, J_val=J_val, dJ=dJ, dM=dm)
    assert min_order > 2.00

    ddJ = Hessian(forward)
    min_order = taylor_test(forward, x, J_val=J_val, ddJ=ddJ, dM=dm,
                            seed=2.0e-2)
    assert min_order > 3.00

    min_order = taylor_test_tlm(forward, x, tlm_order=1, dMs=(dm,))
    assert min_order > 2.00

    min_order = taylor_test_tlm_adjoint(forward, x, adjoint_order=1, dMs=(dm,))
    assert min_order > 2.00

    min_order = taylor_test_tlm_adjoint(forward, x, adjoint_order=2,
                                        dMs=(dm, dm))
    assert min_order > 2.00


@pytest.mark.numpy
def test_SumSolver(setup_test, test_leaks):
    space = FunctionSpace(10)

    def forward(F):
        G = Function(space, name="G")
        AssignmentSolver(F, G).solve()

        J = Functional(name="J")
        SumSolver(G, J.fn()).solve()
        return J

    F = Function(space, name="F", static=True)
    function_set_values(F, np.random.random(function_local_size(F)))

    start_manager()
    J = forward(F)
    stop_manager()

    assert J.value() == function_sum(F)

    dJ = compute_gradient(J, F)
    assert abs(function_get_values(dJ) - 1.0).max() == 0.0


@pytest.mark.numpy
def test_InnerProductSolver(setup_test, test_leaks):
    space = FunctionSpace(10)

    def forward(F):
        G = Function(space, name="G")
        AssignmentSolver(F, G).solve()

        J = Functional(name="J")
        InnerProductSolver(F, G, J.fn()).solve()
        return J

    F = Function(space, name="F", static=True)
    function_set_values(F, np.random.random(function_local_size(F)))

    start_manager()
    J = forward(F)
    stop_manager()

    dJ = compute_gradient(J, F)
    min_order = taylor_test(forward, F, J_val=J.value(), dJ=dJ)
    assert min_order > 1.99


@pytest.mark.numpy
def test_ContractionSolver(setup_test, test_leaks):
    space_0 = FunctionSpace(1)
    space = FunctionSpace(3)
    A = np.array([[1.0, 2.0, 3.0], [0.0, 4.0, 5.0], [0.0, 0.0, 6.0]],
                 dtype=np.float64)

    def forward(m):
        x = Function(space, name="x")
        ContractionSolver(A, (1,), (m,), x).solve()

        norm_sq = Function(space_0, name="norm_sq")
        NormSqSolver(x, norm_sq).solve()

        J = Functional(name="J")
        NormSqSolver(norm_sq, J.fn()).solve()
        return x, J

    m = Function(space, name="m", static=True)
    function_set_values(m, np.array([7.0, 8.0, 9.0], dtype=np.float64))

    start_manager()
    x, J = forward(m)
    stop_manager()

    assert abs(A.dot(m.vector()) - x.vector()).max() == 0.0

    J_val = J.value()

    dJ = compute_gradient(J, m)

    def forward_J(m):
        return forward(m)[1]

    min_order = taylor_test(forward_J, m, J_val=J_val, dJ=dJ)
    assert min_order > 2.00

    ddJ = Hessian(forward_J)
    min_order = taylor_test(forward_J, m, J_val=J_val, ddJ=ddJ)
    assert min_order > 3.00

    min_order = taylor_test_tlm(forward_J, m, tlm_order=1)
    assert min_order > 2.00

    min_order = taylor_test_tlm_adjoint(forward_J, m, adjoint_order=1)
    assert min_order > 2.00

    min_order = taylor_test_tlm_adjoint(forward_J, m, adjoint_order=2)
    assert min_order > 2.00
