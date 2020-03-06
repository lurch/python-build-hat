/* motor.c
 *
 * Copyright (c) Kynesim Ltd, 2020
 *
 * Python class for handling a port's "motor" attribute
 * and attached motors.
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "structmember.h"

#include <stdint.h>

#include "motor.h"
#include "port.h"


/* The actual Motor type */
typedef struct
{
    PyObject_HEAD
    PyObject *port;
    PyObject *device;
} MotorObject;


static int
Motor_traverse(MotorObject *self, visitproc visit, void *arg)
{
    Py_VISIT(self->port);
    Py_VISIT(self->device);
    return 0;
}


static int
Motor_clear(MotorObject *self)
{
    Py_CLEAR(self->port);
    Py_CLEAR(self->device);
    return 0;
}


static void
Motor_dealloc(MotorObject *self)
{
    PyObject_GC_UnTrack(self);
    Motor_clear(self);
    Py_TYPE(self)->tp_free((PyObject *)self);
}


static PyObject *
Motor_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    MotorObject *self = (MotorObject *)type->tp_alloc(type, 0);
    if (self != NULL)
    {
        self->port = Py_None;
        Py_INCREF(Py_None);
        self->device = Py_None;
        Py_INCREF(Py_None);
    }
    return (PyObject *)self;
}


static int
Motor_init(MotorObject *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = { "port", "device" };
    PyObject *port = NULL;
    PyObject *device = NULL;
    PyObject *tmp;

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "OO", kwlist, &port, &device))
        return -1;

    tmp = self->port;
    Py_INCREF(port);
    self->port = port;
    Py_XDECREF(tmp);

    tmp = self->device;
    self->device = device;
    Py_XDECREF(tmp);
    return 0;
}


static PyObject *
Motor_repr(PyObject *self)
{
    MotorObject *motor = (MotorObject *)self;
    int port_id = port_get_id(motor->port);

    return PyUnicode_FromFormat("Motor(%c)", 'A' + port_id);
}


static PyObject *
Motor_get(PyObject *self, PyObject *args)
{
    MotorObject *motor = (MotorObject *)self;
    PyObject *get_fn = PyObject_GetAttrString(motor->device, "get");

    if (get_fn == NULL)
        return NULL;
    return PyObject_CallObject(get_fn, args);
}


static PyMethodDef Motor_methods[] = {
    { "get", Motor_get, METH_VARARGS, "Get as set of readings from the motor" },
    { NULL, NULL, 0, NULL }
};


static PyTypeObject MotorType =
{
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "Motor",
    .tp_doc = "An attached motor",
    .tp_basicsize = sizeof(MotorObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_new = Motor_new,
    .tp_init = (initproc)Motor_init,
    .tp_dealloc = (destructor)Motor_dealloc,
    .tp_traverse = (traverseproc)Motor_traverse,
    .tp_clear = (inquiry)Motor_clear,
    .tp_methods = Motor_methods,
    .tp_repr = Motor_repr
};


int motor_modinit(void)
{
    if (PyType_Ready(&MotorType) < 0)
        return -1;
    Py_INCREF(&MotorType);
    return 0;
}


void motor_demodinit(void)
{
    Py_DECREF(&MotorType);
}


PyObject *motor_new_motor(PyObject *port, PyObject *device)
{
    PyObject *args = Py_BuildValue("(OO)", port, device);

    if (args == NULL)
        return NULL;
    return PyObject_CallObject((PyObject *)&MotorType, args);
}
