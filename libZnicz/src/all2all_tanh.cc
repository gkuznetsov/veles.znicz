/*! @file all2all_tanh.cc
 *  @brief "All to all" neural network layer with Tanh activation function
 *  @author Ernesto Sanches <ernestosanches@gmail.com>
 *  @version 1.0
 *
 *  @section Notes
 *  This code partially conforms to <a href="http://google-styleguide.googlecode.com/svn/trunk/cppguide.xml">Google C++ Style Guide</a>.
 *
 *  @section Copyright
 *  Copyright 2013 Samsung R&D Institute Russia
 */


#include <cmath>
#include <simd/memory.h>
#include <simd/arithmetic-inl.h>
#include "src/all2all_tanh.h"

namespace Veles {
namespace Znicz {

void All2AllTanh::ApplyActivationFunction(float* data, size_t length) const {
  std::unique_ptr<float[], void (*)(void*)> tmp(
      mallocf(length), std::free);
  real_multiply_scalar(data, length, kScaleX, tmp.get());
  for(size_t i = 0; i < length; ++i) {
    tmp[i] = std::tanh(tmp[i]);
  }
  real_multiply_scalar(tmp.get(), length, kScaleY, data);
}

}  // namespace Znicz
}  // namespace Veles