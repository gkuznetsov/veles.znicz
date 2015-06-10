#include "defines.cl"
#include "highlight.cl"


{% set blocks_number = ((max_batch_size + 0.0) / block_size) | round(0, "ceil") | int %}


/// @brief Evaluate softmax.
/// @param y output of the last layer with applied softmax.
/// @param max_idx index of maximum element for each sample in batch.
/// @param labels labels for samples in batch.
/// @param batch_size size of the current batch.
/// @param multiplier coefficient to multiply backpropagated error on.
/// @param n_err [0] - n_err.
/// @param confusion_matrix confusion matrix (may be NULL).
/// @param max_err_y_sum maximum sum of backpropagated gradient norms.
/// @param err_y output error for backpropagation.
/// @details We will launch a single workgroup here.

__kernel __attribute__((reqd_work_group_size({{ block_size }}, 1, 1)))
void evaluate_softmax(__global const dtype /* IN */ *y,
                      __global const int /* IN */ *max_idx,
                      __global const int /* IN */ *labels,
                      const int /* IN */ batch_size,
                      const dtype /* IN */ multiplier,
                      __global int /* IN, OUT */ *n_err,
                      __global int /* IN, OUT */ *confusion_matrix,
                      __global dtype /* IN, OUT */ *max_err_y_sum,
                      __global dtype /* OUT */ *err_y) {
  __local int IM[{{ block_size }}], IREAL[{{ block_size }}];
  __local dtype SM[{{ block_size }}];
  int tx = get_local_id(0);
  int i_sample = tx;
  int y_start = i_sample * {{ output_size }};
  int n_ok = 0;
  dtype _max_err_y_sum = 0;

  // Compute err_y and fill the confusion matrix
  for (int i = 0; i < {{ blocks_number }}; i++,
       i_sample += {{ block_size }},
       y_start += {{ output_size }} * {{ block_size }}) {
    dtype err_y_sum = 0;
    int ireal = labels[i_sample];
    if ((i_sample < batch_size) && (ireal >= 0)) {
      int im = max_idx[i_sample];

      IM[tx] = im;
      IREAL[tx] = ireal;

      if (im == ireal) {
        n_ok++;
      }
      dtype vle;
      for (int j = 0; j < ireal; j++) {
        vle = y[y_start + j];
        vle *= multiplier;
        err_y[y_start + j] = vle;
        err_y_sum += fabs(vle);
      }

      vle = y[y_start + ireal] - 1;
      vle *= multiplier;
      err_y[y_start + ireal] = vle;
      err_y_sum += fabs(vle);

      for (int j = ireal + 1; j < {{ output_size }}; j++) {
        vle = y[y_start + j];
        vle *= multiplier;
        err_y[y_start + j] = vle;
        err_y_sum += fabs(vle);
      }
    } else if (i_sample < {{ max_batch_size }}) { // set excessive gradients to zero
      for (int j = 0; j < {{ output_size }}; j++)
        err_y[y_start + j] = 0;
    }
    _max_err_y_sum = max(_max_err_y_sum, err_y_sum);

    // Update confusion matrix
    barrier(CLK_LOCAL_MEM_FENCE);
    if ((!tx) && (confusion_matrix) && (i_sample < batch_size)) {
      int n = batch_size - i_sample;
      if (n > {{ block_size }})
        n = {{ block_size }};
      for (int j = 0; j < n; j++)
        confusion_matrix[IM[j] * {{ output_size }} + IREAL[j]]++;
    }
    barrier(CLK_LOCAL_MEM_FENCE);
  }
 
  // Compute n_err, max_err_y_sum
  IM[tx] = n_ok;
  SM[tx] = _max_err_y_sum;
  barrier(CLK_LOCAL_MEM_FENCE);
  if (!tx) {
    n_ok = IM[0];
    _max_err_y_sum = SM[tx];
    for (int j = 1; j < {{ block_size }}; j++) {
      n_ok += IM[j];
      _max_err_y_sum = max(_max_err_y_sum, SM[j]);
    }
    n_err[0] += batch_size - n_ok;
    max_err_y_sum[0] = max(_max_err_y_sum, max_err_y_sum[0]);
  }
}


/// @brief Evaluate MSE.
/// @param y output of the last layer.
/// @param target target values.
/// @param batch_size size of the current batch.
/// @param multiplier coefficient to multiply backpropagated error on.
/// @param metrics [0] - sum of sample's mse, [1] - max of sample's mse, [2] - min of sample's mse.
/// @param err_y output error for backpropagation.
/// @param mse sample's mse.
/// @details We will launch a single workgroup here.

__kernel __attribute__((reqd_work_group_size({{ block_size }}, 1, 1)))
void evaluate_mse(__global const dtype /* IN */ *y,
                  __global const dtype /* IN */ *target,
                  const int /* IN */ batch_size,
                  const dtype /* IN */ multiplier,
                  __global dtype /* IN, OUT */ *metrics,
                  __global dtype /* OUT */ *mse,
                  __global dtype /* OUT */ *err_y) {
  __local dtype SM[{{ block_size }}], SM1[{{ block_size }}], SM2[{{ block_size }}];
  int tx = get_local_id(0);
  int i_sample = tx;
  int y_start = i_sample * {{ output_size }};
  dtype mse_sum = 0, mse_max = 0, mse_min = MAXFLOAT;
 
  // Compute err_y and fill the confusion matrix
  for (int i = 0; i < {{ blocks_number }}; i++,
       i_sample += {{ block_size }},
       y_start += {{ output_size }} * {{ block_size }}) {
    if (i_sample < batch_size) {
      dtype vle, vle_target;
      dtype sample_sse = 0;
      for (int j = 0; j < {{ output_size }}; j++) {
        vle = y[y_start + j];
        vle_target = target[y_start + j];
        vle -= vle_target;
        sample_sse += vle * vle;
        vle *= multiplier;
        err_y[y_start + j] = vle;
      }
      {% if root %}
        dtype sample_mse = sqrt(sample_sse / {{ output_size }});
      {% else %}
        dtype sample_mse = sample_sse / {{ output_size }};
      {% endif %}
      mse[i_sample] = sample_mse;
      mse_sum += sample_mse;
      mse_max = max(mse_max, sample_mse);
      mse_min = min(mse_min, sample_mse);
    } else if (i_sample < {{ max_batch_size }}) {
      for (int j = 0; j < {{ output_size }}; j++) {
        err_y[y_start + j] = 0;
      }
      mse[i_sample] = 0;
    }
  }
  // Compute metrics
  SM[tx] = mse_sum;
  SM1[tx] = mse_max;
  SM2[tx] = mse_min;
  barrier(CLK_LOCAL_MEM_FENCE);
  if (!tx) {
    mse_sum = SM[tx];
    mse_max = SM1[tx];
    mse_min = SM2[tx];
    for (int j = 1; j < {{ block_size }}; j++) {
      mse_sum += SM[j];
      mse_max = max(mse_max, SM1[j]);
      mse_min = min(mse_min, SM2[j]);
    }
    metrics[0] += mse_sum;
    metrics[1] = max(metrics[1], mse_max);
    metrics[2] = min(metrics[2], mse_min);
  }
}