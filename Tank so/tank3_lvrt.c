/*
tank3_lvrt.c
LabVIEW CLFN-compatible C version of tank3.py for NI Linux RT / .so deployment.

Source behavior derived from tank3.py and CLFN packaging rules from the attached LabVIEW C/.so prompt spec.

CLFN terminal order (frozen once released):
  1.  Valve_pos              double      Value
  2.  dt                     double      Value
  3.  range_vals             double*     Array Data Pointer, length 2
  4.  initial_level          double      Value
  5.  process_params         double*     Array Data Pointer, length 7
  6.  state_in               double      Value
  7.  measured_level         double*     Pointer to Value
  8.  flow_in                double*     Pointer to Value
  9.  flow_out               double*     Pointer to Value
  10. state_out              double*     Pointer to Value
*/

#include <math.h>
#include <stdint.h>
#include <stddef.h>

#ifdef _WIN32
  #define EXPORT __declspec(dllexport)
#else
  #define EXPORT __attribute__((visibility("default")))
#endif

static double clamp_double(double x, double lo, double hi) {
    if (x < lo) return lo;
    if (x > hi) return hi;
    return x;
}

EXPORT void tank_model_solve(
    double Valve_pos,
    double dt,
    const double *range_vals,
    double initial_level,
    const double *process_params,
    double state_in,
    double *measured_level,
    double *flow_in,
    double *flow_out,
    double *state_out
) {
    const double tank_max = 100.0;
    const double tank_min = 0.0;
    const double plant_noise = 0.0;

    double output_high, output_low;
    double static_gain, lag, deadtime, load, deadband, sensor_noise, leak_rate_half_full;
    double prev_level, leak_flow, k, new_level, measured;

    if (range_vals == NULL || process_params == NULL ||
        measured_level == NULL || flow_in == NULL ||
        flow_out == NULL || state_out == NULL) {
        return;
    }

    output_high = (double)range_vals[0];
    output_low  = (double)range_vals[1];

    static_gain          = (double)process_params[0];
    lag                  = (double)process_params[1];
    deadtime             = (double)process_params[2];
    load                 = (double)process_params[3];
    deadband             = (double)process_params[4];
    sensor_noise         = (double)process_params[5];
    leak_rate_half_full  = (double)process_params[6];

    (void)lag;
    (void)deadtime;
    (void)sensor_noise;
    (void)plant_noise;

    if (state_in < 0.0) {
        prev_level = initial_level;
    } else {
        prev_level = state_in;
    }

    if (fabs(Valve_pos) < deadband) {
        Valve_pos = 0.0;
    }

    Valve_pos = clamp_double(Valve_pos, 0.0, 100.0);

    *flow_in = static_gain * Valve_pos / 100.0;

    if (prev_level <= 0.0) {
        leak_flow = 0.0;
    } else {
        k = leak_rate_half_full / sqrt(0.5);
        leak_flow = k * sqrt(prev_level / tank_max);
    }

    *flow_out = leak_flow + load;

    new_level = prev_level + ((*flow_in) - (*flow_out)) * dt;
    new_level = clamp_double(new_level, tank_min, tank_max);

    measured = new_level;
    measured = clamp_double(measured, output_low, output_high);

    *measured_level = measured;
    *state_out = new_level;
}

#ifdef TANK3_SMOKE_TEST
#include <stdio.h>
#include <stdlib.h>

static int nearly_equal(double a, double b, double tol) {
    double err = fabs(a - b);
    return err <= tol;
}

int main(void) {
    int all_ok = 1;

    {
        double range_vals[2] = {100.0, 0.0};
        double process_params[7] = {1.5, 18.0, 1.0, 0.0, 1.0, 0.0, 5.0};
        double measured_level = 0.0;
        double flow_in = 0.0;
        double flow_out = 0.0;
        double state_out = 0.0;

        tank_model_solve(
            50.0,
            0.1,
            range_vals,
            30.0,
            process_params,
            -1.0,
            &measured_level,
            &flow_in,
            &flow_out,
            &state_out
        );

        all_ok &= nearly_equal(flow_in, 0.75, 1e-12);
        all_ok &= nearly_equal(flow_out, 3.872983346207417, 1e-12);
        all_ok &= nearly_equal(state_out, 29.687701665379258, 1e-12);
        all_ok &= nearly_equal(measured_level, state_out, 1e-12);

        printf("case1 measured=%.12f flow_in=%.12f flow_out=%.12f state=%.12f  %s\n",
               measured_level, flow_in, flow_out, state_out, all_ok ? "PASS" : "FAIL");
    }

    {
        double range_vals[2] = {100.0, 0.0};
        double process_params[7] = {1.5, 18.0, 1.0, 0.0, 1.0, 0.0, 5.0};
        double measured_level = 0.0;
        double flow_in = 0.0;
        double flow_out = 0.0;
        double state_out = 0.0;

        tank_model_solve(
            0.5,
            0.1,
            range_vals,
            30.0,
            process_params,
            -1.0,
            &measured_level,
            &flow_in,
            &flow_out,
            &state_out
        );

        all_ok &= nearly_equal(flow_in, 0.0, 1e-12);

        printf("case2 deadband flow_in=%.12f  %s\n",
               flow_in, nearly_equal(flow_in, 0.0, 1e-12) ? "PASS" : "FAIL");
    }

    printf("OVERALL: %s\n", all_ok ? "PASS" : "FAIL");
    return all_ok ? 0 : 1;
}
#endif
