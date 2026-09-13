# Nordic Edge AI Lab solution deployment

[**Nordic Edge AI Lab:**](https://www.nordicsemi.com/Products/Technologies/Edge-AI/Get-Started#:~:text=Nordic%20Edge%20AI%20Lab) Nordic’s Edge AI Lab is a no-code platform that “transforms your sensor data into compact, high-performance AI models ready to deploy on Nordic’s ultra-low-power SoCs and SiPs in just minutes”. 

Using the Lab, you upload a dataset and it generates a ZIP archive containing artifacts and folder named `nrf_edgeai_generated` with all the C source and header files for your specific solution. This generated folder includes files such as:

- `nrf_edgeai_user_model.c` – User model definitions and structures.
- `nrf_edgeai_user_model.h` – Header declaring the user model interface.
- `nrf_edgeai_user_types.h` – Data type definitions for model inputs/outputs.
- `prj_example.conf` – Example Zephyr prj.conf settings (enabling Edge AI and Axon in the sdk-edge-ai add-on).

**Optional headears**
- `nrf_edgeai_user_model_axon.h` – NPU-specific model definition, generated only if Axon/NPU mode was used.
- `nrf_edgeai_user_model_labels.h` - Optional user labels file with enum and string definitions, generated only for Wakeword, KeyWords Spotting solutions.

You should extract or copy this `nrf_edgeai_generated` folder into your application’s source tree (for example under `src/`), so that it is built together with your firmware.

## nRF Edge AI Add-on (nrf_edgeai, nrf_axon)

The generated code is *model-specific* only – you still need the inference runtime libraries. Nordic provides the [Edge AI Add-on](https://github.com/nrfconnect/sdk-edge-ai) for nRF Connect SDK, which supplies the `nrf_edgeai` and `nrf_axon` libraries. The Edge AI Add-on is “a compact add-on that makes it easy to run small, generated machine-learning models on Nordic Semiconductor devices”. You must install this add-on separately (for example via nRF Connect for VS Code) to get the actual inference engines.

Please refer to the [add-on documentation](https://docs.nordicsemi.com/bundle/addon-edge-ai_latest/page/index.html) to find more about how to integrate and work with `nrf_edgeai` and `nrf_axon` libraries


# Standard Neuton (CPU) vs. Axon (NPU) Inference

Depends on user solution setting, generated models can run on the CPU (Neuton) or NPU (Axon) using the `nrf_edgeai` library. The Axon core is a dedicated AI accelerator that can speed up inference up to ~15× faster than `tflite-micro` CPU inference engine.

The same `nrf_edgeai` API is used both for CPU or NPU inference – you still call the same functions – but internally the model executes on the Axon NPU instead CPU, the user-facing API does not change between CPU Neuton and NPU Axon modes, but the build/link settings differ. Please refer to the [add-on documentation](https://docs.nordicsemi.com/bundle/addon-edge-ai_latest/page/index.html) for more information.

# Using the nRF EdgeAI API

For making an inference with nRF EdgeAI, there are only 4 functions that you should use:
* `nrf_edgeai_user_model` - Get user model pointer;
* `nrf_edgeai_init` - Set up the internal components of nRF EdgeAI Lab user model, **should be called first and once**;
* `nrf_edgeai_feed_inputs` - Feed and prepare live input features for model inference;
* `nrf_edgeai_run_inference` - Run live input features into a nRF EdgeAI machine learning algorithm (or “ML/NN model”) to inference an output;

To run the solution in the firmware, follow these steps:

1. **Include headers** in your C source, include the Edge AI headers and your model header:

``` C
#include <nrf_edgeai/nrf_edgeai.h>
#include <nrf_edgeai_generated/nrf_edgeai_user_model.h>
```

2. **Get model pointer and initialize**, call `nrf_edgeai_user_model()` to get a pointer to the model context, then initialize it:
``` C
nrf_edgeai_t* p_model = nrf_edgeai_user_model();
nrf_edgeai_err_t res = nrf_edgeai_init(p_model);
// Optional check for success, #include <assert.h> required
assert(res == NRF_EDGEAI_ERR_SUCCESS);
```

3. **Prepare input data.** Collect raw input features (e.g. sensor readings) into a buffer in the same order and format as the training data.

4. **Feed inputs.** Call `nrf_edgeai_feed_inputs(p_model, data, len)` to feed the inputs into the model. If your model uses windowed input (sample-by-sample accumulation), nrf_edgeai_feed_inputs will buffer internally until a full window is ready. For example:
``` C
// Example: feeding an array of int16_t features
int16_t raw_features[] = { Accelerometer_X0, Accelerometer_Y0, Accelerometer_Z0, /*...*/ };

uint32_t num_input_feats = nrf_edgeai_uniq_inputs_num(p_model);
nrf_edgeai_err_t feed_res = nrf_edgeai_feed_inputs(p_model, raw_features, num_input_feats);

if (feed_res == NRF_EDGEAI_ERR_SUCCESS) {
    // inputs are collected and ready for inference
}
```

5. **Run inference.** When inputs are ready, invoke the inference function:
``` C

nrf_edgeai_err_t inf_res = nrf_edgeai_run_inference(p_model);

if (inf_res == NRF_EDGEAI_ERR_SUCCESS) {
    // inference results are ready
}
```

6. **Read outputs.** After a successful inference, the results are in *p_model->decoded_output*.

For example:
- For classification: *model->decoded_output.classif.predicted_class* and probabilities in *model->decoded_output.classif.probabilities*.

- For regression: output values in *model->decoded_output.regression.p_outputs* (array of predicted values).

- For anomaly: anomaly score in *model->decoded_output.anomaly.score*.

## Examples

Below are example code snippets illustrating end-to-end inference for different model tasks. (These reuse the feeding/inference logic above.)

### Classification

```C
#include <nrf_edgeai/nrf_edgeai.h>
#include <nrf_edgeai_generated/nrf_edgeai_user_model.h>
#include <assert.h>
#include <stdio.h>
// In this example, our raw features is a window of N elements with 3 accelerometer axis values
// The number of raw features and their order should be the same as in the training dataset file
int16_t raw_features[] = 
{
    Accelerometer_X0,
    Accelerometer_Y0,
    Accelerometer_Z0,
    /* ... */
    Accelerometer_Xn,
    Accelerometer_Yn,
    Accelerometer_Zn,
};
// Pointer to user model
static nrf_edgeai_t* p_edgeai = NULL;

void user_init_edegeai_model(void)
{
    // Get user model pointer
    p_edgeai = nrf_edgeai_user_model();
    // Init EdgeAI library based on user solution, should be called once!
    nrf_edgeai_err_t res = nrf_edgeai_init(p_edgeai);
    // Optional check for success, #include <assert.h> required
    assert(res == NRF_EDGEAI_ERR_SUCCESS);
}
//
// ....
//
void user_feed_data_to_model(void)
{
    // Feed and prepare raw inputs for the model inference
    nrf_edgeai_err_t res = nrf_edgeai_feed_inputs(p_edgeai, raw_features, 
                                            nrf_edgeai_uniq_inputs_num(p_edgeai) * 
                                            nrf_edgeai_input_window_size(p_edgeai));

    // Check if input data is prepared and ready for model inference
    if (res == NRF_EDGEAI_ERR_SUCCESS)
    {
        // Run model inference
        res = nrf_edgeai_run_inference(p_edgeai);
        // Check if model inference is ready and successful
        if (res == NRF_EDGEAI_ERR_SUCCESS)
        {
            uint16_t predicted_class = p_edgeai->decoded_output.classif.predicted_class;
            size_t num_classes = p_edgeai->decoded_output.classif.num_classes;
            // Get probability depending on model quantization: f32, q16, q8. Here is an example for f32 model
            const flt32_t* p_probabilities = p_edgeai->decoded_output.classif.probabilities.p_f32;

            printf("Predicted class %u with probability %f, in %u classes\r\n", predicted_class, 
                                                                                p_probabilities[predicted_class],
                                                                                num_classes);
        }
    }
    
}
```

### Regression

```C
#include <nrf_edgeai/nrf_edgeai.h>
#include <nrf_edgeai_generated/nrf_edgeai_user_model.h>
#include <assert.h>
#include <stdio.h>
// In this example, our raw features is a window of N elements with 3 accelerometer axis values
// The number of raw features and their order should be the same as in the training dataset file
int16_t raw_features[] = 
{
    Accelerometer_X0,
    Accelerometer_Y0,
    Accelerometer_Z0,
    /* ... */
    Accelerometer_Xn,
    Accelerometer_Yn,
    Accelerometer_Zn,
};
// Pointer to user model
static nrf_edgeai_t* p_edgeai = NULL;

void user_init_edegeai_model(void)
{
    // Get user model pointer
    p_edgeai = nrf_edgeai_user_model();
    // Init EdgeAI library based on user solution, should be called once!
    nrf_edgeai_err_t res = nrf_edgeai_init(p_edgeai);
    // Optional check for success, #include <assert.h> required
    assert(res == NRF_EDGEAI_ERR_SUCCESS);
}
//
// ....
//
void user_feed_data_to_model(void)
{
    // Feed and prepare raw inputs for the model inference
    nrf_edgeai_err_t res = nrf_edgeai_feed_inputs(p_edgeai, raw_features, 
                                            nrf_edgeai_uniq_inputs_num(p_edgeai) * 
                                            nrf_edgeai_input_window_size(p_edgeai));

    // Check if input data is prepared and ready for model inference
    if (res == NRF_EDGEAI_ERR_SUCCESS)
    {
        // Run model inference
        res = nrf_edgeai_run_inference(p_edgeai);
        // Check if model inference is ready and successful
        if (res == NRF_EDGEAI_ERR_SUCCESS)
        {
            const flt32_t* p_predicted_values = p_edgeai->decoded_output.regression.p_outputs;
            size_t values_num = p_edgeai->decoded_output.regression.outputs_num;

            printf("Predicted target values:\r\n");
            for (size_t i = 0; i < values_num; i++)
            {
                printf("%f,", p_predicted_values[i]);
            }
            printf("\r\n");
        }
    }
    
}
```

### Anomaly detection

In anomaly detection mode, the model's inference yields an Anomaly Score, indicating the similarity of input data to the "normal" data used for training. A higher Anomaly Score signifies greater deviation from the normal data, while a score close to zero indicates normal data. Because the model learns only from normal data, it cannot predict the presence of anomalies, only deviation from the normal data, so user must set a threshold based on the Anomaly Score to identify anomalies.

```C
#include <nrf_edgeai/nrf_edgeai.h>
#include <nrf_edgeai_generated/nrf_edgeai_user_model.h>
#include <assert.h>
#include <stdio.h>
// User should define Anomaly Score Threshold to identify anomalies by himself,
// specific to user application
#define USER_DEFINED_ANOMALY_SCORE_THRESHOLD 0.6f
// In this example, our raw features is a window of N elements with 3 accelerometer axis values
// The number of raw features and their order should be the same as in the training dataset file
int16_t raw_features[] = 
{
    Accelerometer_X0,
    Accelerometer_Y0,
    Accelerometer_Z0,
    /* ... */
    Accelerometer_Xn,
    Accelerometer_Yn,
    Accelerometer_Zn,
};
// Pointer to user model
static nrf_edgeai_t* p_edgeai = NULL;

void user_init_edegeai_model(void)
{
    // Get user model pointer
    p_edgeai = nrf_edgeai_user_model();
    // Init EdgeAI library based on user solution, should be called once!
    nrf_edgeai_err_t res = nrf_edgeai_init(p_edgeai);
    // Optional check for success, #include <assert.h> required
    assert(res == NRF_EDGEAI_ERR_SUCCESS);
}
//
// ....
//
void user_feed_data_to_model(void)
{
    // Feed and prepare raw inputs for the model inference
    nrf_edgeai_err_t res = nrf_edgeai_feed_inputs(p_edgeai, raw_features, 
                                            nrf_edgeai_uniq_inputs_num(p_edgeai) * 
                                            nrf_edgeai_input_window_size(p_edgeai));

    // Check if input data is prepared and ready for model inference
    if (res == NRF_EDGEAI_ERR_SUCCESS)
    {
        // Run model inference
        res = nrf_edgeai_run_inference(p_edgeai);
        // Check if model inference is ready and successful
        if (res == NRF_EDGEAI_ERR_SUCCESS)
        {
            flt32_t anomaly_score = p_edgeai->decoded_output.anomaly.score;

            printf("Predicted Anomaly score: %f\r\n", anomaly_score);

            if (anomaly_score > USER_DEFINED_ANOMALY_SCORE_THRESHOLD)
            {
                printf("Anomaly detected!\n");
            }
        }
    }
}
```

### Additional solution information API

You can use the following API to get solution information:
* `nrf_edgeai_solution_id_str` - Get user solution ID in string format;
* `nrf_edgeai_uniq_inputs_num` - Get number of unique input features on which the model was trained;
* `nrf_edgeai_input_window_size` - Get input features window size in feature samples(vectors);
* `nrf_edgeai_model_outputs_num` - Get number of model outputs (predicted targets);
* `nrf_edgeai_model_task` - Get model task, e.g. NRF_EDGEAI_TASK_BIN_CLASS, NRF_EDGEAI_TASK_REGRESSION
* `nrf_edgeai_model_type` - Get model type, NRF_EDGEAI_MODEL_NEUTON or NRF_EDGEAI_MODEL_AXON