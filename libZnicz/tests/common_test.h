/*! @file common_test.h
 *  @brief Common test functionality.
 *  @author Ernesto Sanches <ernestosanches@gmail.com>
 *  @version 1.0
 *
 *  @section Notes
 *  This code partially conforms to <a href="http://google-styleguide.googlecode.com/svn/trunk/cppguide.xml">Google C++ Style Guide</a>.
 *
 *  @section Copyright
 *  Copyright 2013 Samsung R&D Institute Russia
 */

#ifndef COMMON_TEST_H_
#define COMMON_TEST_H_

#include <memory>
#include <gtest/gtest.h>
#include <veles/unit.h>
#include <veles/unit_factory.h>
#include <simd/inc/simd/memory.h>

class CommonTest : public ::testing::Test {
 protected:
  static const float kValueZero;
  static const float kValueOne;
  static const float kValueInputInit;
  static const float kValueOutputInit;
  static const float kValueOther;

  static std::shared_ptr<float> CreateFloatArray(
      size_t count, float initializer = kValueZero) {
    auto ptr = std::shared_ptr<float>(mallocf(count), std::free);
    memsetf(ptr.get(), count, initializer);
    return ptr;
  }

  static std::shared_ptr<Veles::Unit> CreateUnit(const std::string& name) {
    return Veles::UnitFactory::Instance()[name]();
  }

  static void InitializeUnit(std::shared_ptr<Veles::Unit> unit,
                             size_t inputs, size_t outputs,
                             float* weights = nullptr, float* bias = nullptr) {
    auto weights_array = CreateFloatArray(inputs * outputs);
    auto bias_array = CreateFloatArray(outputs);
    if (weights) {
      memcpy(weights_array.get(), weights, inputs * outputs * sizeof(float));
    }
    if (bias) {
      memcpy(bias_array.get(), bias, outputs * sizeof(float));
    }
    unit->SetParameter("weights", weights_array);
    unit->SetParameter("bias", bias_array);
    unit->SetParameter("inputs", std::make_shared<size_t>(inputs));
    unit->SetParameter("outputs", std::make_shared<size_t>(outputs));
  }
};

const float CommonTest::kValueZero = 0;
const float CommonTest::kValueOne = 1;
const float CommonTest::kValueInputInit = 42.42;
const float CommonTest::kValueOutputInit = 412.31415;
const float CommonTest::kValueOther = 156.27172;

#endif  // TEST_COMMON_H_