# Copyright (c) 2022 Graphcore Ltd. All rights reserved.

import numpy as np
import pytest
import tensorflow as tf
import tensorflow_addons as tfa

from model.loss_accuracy import (MaskedBinaryMultiLabelAccuracy,
                                 MaskedBinaryMultiLabelCrossentropy,
                                 MaskedBinaryMultiLabelF1Score,
                                 MaskedCategoricalAccuracy,
                                 MaskedCategoricalCrossentropy,
                                 MaskedCategoricalF1Score,
                                 get_mask_from_labels,
                                 set_masked_elements_to_zero)


@pytest.mark.parametrize(
    "labels,expected_mask",
    [(np.array([[0, 1, 1],
                [0, 0, 1],
                [0, 1, 1],
                [-1, -1, -1],
                [-1, -1, -1]]),
      np.array([True, True, True, False, False])),
     (np.array([[0, 1, 1],
                [0, 0, 1],
                [0, 1, 1]]),
      np.array([True, True, True])),
     (np.array([[-1, -1, -1]]),
      np.array([False]))])
def test_get_mask_from_labels(labels, expected_mask):
    mask = get_mask_from_labels(labels)
    np.testing.assert_equal(mask, expected_mask)


@pytest.mark.parametrize(
    "labels,mask,expected_labels_masked",
    [(np.array([[0, 1, 1],
                [0, 0, 1],
                [0, 1, 1],
                [-1, -1, -1],
                [-1, -1, -1]]),
      np.array([True, True, True, False, False]),
      np.array([[0, 1, 1],
                [0, 0, 1],
                [0, 1, 1],
                [0, 0, 0],
                [0, 0, 0]])),
     (np.array([[-1, -1, -1]]),
      np.array([False]),
      np.array([[0, 0, 0]]))])
def test_set_masked_elements_to_zero(labels,
                                     mask,
                                     expected_labels_masked):
    labels_masked = set_masked_elements_to_zero(labels,
                                                mask)
    np.testing.assert_equal(labels_masked, expected_labels_masked)


def test_masked_loss_bce():
    labels_unmasked = np.array([[0, 1, 1],
                                [0, 0, 1],
                                [0, 1, 1]])
    y_pred_unmasked = np.array([[0.05, 0.81, 0.14],
                                [0.1, 0.8, 0.1],
                                [0.05, 0.49, 0.51]],
                               dtype=np.float32)

    labels_masked = np.array([[0, 1, 1],
                              [0, 0, 1],
                              [0, 1, 1],
                              [-1, -1, -1],
                              [-1, -1, -1]])
    y_pred_masked = np.array([[0.05, 0.81, 0.14],
                              [0.1, 0.8, 0.1],
                              [0.05, 0.49, 0.51],
                              [0.1, 0.8, 0.1],
                              [0.05, 0.95, 0]], dtype=np.float32)

    y_pred_unmasked = tf.math.sigmoid(y_pred_unmasked)
    loss_fn_unmasked = tf.keras.losses.BinaryCrossentropy(from_logits=False)
    loss_unmasked = loss_fn_unmasked(labels_unmasked, y_pred_unmasked)

    loss_fn_masked = MaskedBinaryMultiLabelCrossentropy(from_logits=False,
                                                        reduction=tf.keras.losses.Reduction.NONE)
    loss_masked = loss_fn_masked(labels_masked, y_pred_masked)

    expected_loss = 0.6598439
    np.testing.assert_almost_equal(loss_unmasked, expected_loss)
    np.testing.assert_almost_equal(loss_masked, expected_loss)


def test_masked_loss_cce():
    labels_unmasked = np.array([[0, 1, 0], [0, 0, 1]])
    y_pred_unmasked = np.array([[0.05, 0.95, 0], [0.1, 0.8, 0.1]],
                               dtype=np.float32)

    labels_masked = np.array([[0, 1, 0],
                              [0, 0, 1],
                              [-1, -1, -1],
                              [-1, -1, -1]])
    y_pred_masked = np.array([[0.05, 0.95, 0],
                              [0.1, 0.8, 0.1],
                              [0.1, 0.8, 0.1],
                              [0.05, 0.95, 0]], dtype=np.float32)

    loss_fn_unmasked = tf.keras.losses.CategoricalCrossentropy(from_logits=True)
    loss_unmasked = loss_fn_unmasked(labels_unmasked, y_pred_unmasked)

    loss_fn_masked = MaskedCategoricalCrossentropy(from_logits=True,
                                                   reduction=tf.keras.losses.Reduction.NONE)
    loss_masked = loss_fn_masked(labels_masked, y_pred_masked)

    expected_loss = 0.9868951
    np.testing.assert_almost_equal(loss_unmasked, expected_loss)
    np.testing.assert_almost_equal(loss_masked, expected_loss)


def test_masked_accuracy_bce():
    labels_unmasked = np.array([[0, 1, 1],
                                [0, 0, 1],
                                [0, 1, 1]])
    y_pred_unmasked = np.array([[0.05, 0.81, 0.14],
                                [0.1, 0.8, 0.1],
                                [0.05, 0.49, 0.51]],
                               dtype=np.float32)

    labels_masked = np.array([[0, 1, 1],
                              [0, 0, 1],
                              [0, 1, 1],
                              [-1, -1, -1],
                              [-1, -1, -1]])
    y_pred_masked = np.array([[0.05, 0.81, 0.14],
                              [0.1, 0.8, 0.1],
                              [0.05, 0.49, 0.51],
                              [0.1, 0.8, 0.1],
                              [0.05, 0.95, 0]], dtype=np.float32)

    y_pred_unmasked = tf.math.sigmoid(y_pred_unmasked)
    accuracy_unmasked = tf.keras.metrics.BinaryAccuracy()
    accuracy_unmasked.update_state(labels_unmasked,
                                   y_pred_unmasked)

    accuracy_masked = MaskedBinaryMultiLabelAccuracy()
    accuracy_masked.update_state(labels_masked,
                                 y_pred_masked)

    expected_accuracy = 0.5555555
    np.testing.assert_almost_equal(accuracy_unmasked.result().numpy(),
                                   expected_accuracy)
    np.testing.assert_almost_equal(accuracy_masked.result().numpy(),
                                   expected_accuracy)


def test_masked_accuracy_cce():
    labels_unmasked = np.array([[0, 1, 0], [0, 0, 1]])
    y_pred_unmasked = np.array([[0.05, 0.95, 0], [0.1, 0.8, 0.1]],
                               dtype=np.float32)

    labels_masked = np.array([[0, 1, 0],
                              [0, 0, 1],
                              [-1, -1, -1],
                              [-1, -1, -1]])
    y_pred_masked = np.array([[0.05, 0.95, 0],
                              [0.1, 0.8, 0.1],
                              [0.1, 0.8, 0.1],
                              [0.05, 0.95, 0]], dtype=np.float32)

    accuracy_unmasked = tf.keras.metrics.CategoricalAccuracy()
    accuracy_unmasked.update_state(labels_unmasked,
                                   y_pred_unmasked)

    accuracy_masked = MaskedCategoricalAccuracy()
    accuracy_masked.update_state(labels_masked,
                                 y_pred_masked)

    expected_accuracy = 0.5
    np.testing.assert_almost_equal(accuracy_unmasked.result().numpy(),
                                   expected_accuracy)
    np.testing.assert_almost_equal(accuracy_masked.result().numpy(),
                                   expected_accuracy)


def test_masked_f1_score_binary_multi_label():
    labels_unmasked = np.array([[0, 1, 1],
                                [0, 0, 1],
                                [0, 1, 1]])
    y_pred_unmasked = np.array([[0.05, 0.81, 0.14],
                                [0.1, 0.8, 0.1],
                                [0.05, 0.49, 0.51]],
                               dtype=np.float32)

    labels_masked = np.array([[0, 1, 1],
                              [0, 0, 1],
                              [0, 1, 1],
                              [-1, -1, -1],
                              [-1, -1, -1]])
    y_pred_masked = np.array([[0.05, 0.81, 0.14],
                              [0.1, 0.8, 0.1],
                              [0.05, 0.49, 0.51],
                              [0.1, 0.8, 0.1],
                              [0.05, 0.95, 0]], dtype=np.float32)

    y_pred_unmasked = tf.math.sigmoid(y_pred_unmasked)
    f1_score_unmasked = tfa.metrics.F1Score(num_classes=3,
                                            average="macro",
                                            threshold=0.5)
    f1_score_unmasked.update_state(np.array(labels_unmasked),
                                   np.array(y_pred_unmasked))

    f1_score_masked = MaskedBinaryMultiLabelF1Score(num_classes=3,
                                                    metrics_precision=tf.float32,
                                                    average="macro")
    f1_score_masked.update_state(np.array(labels_masked),
                                 np.array(y_pred_masked))

    expected_f1_score = 0.59999996
    np.testing.assert_almost_equal(f1_score_unmasked.result().numpy(),
                                   expected_f1_score)
    np.testing.assert_almost_equal(f1_score_masked.result().numpy(),
                                   expected_f1_score)


def test_masked_f1_score_cce():
    labels_unmasked = np.array([[0, 1, 0], [0, 0, 1]])
    y_pred_unmasked = np.array([[0.05, 0.95, 0], [0.1, 0.8, 0.1]],
                               dtype=np.float32)

    labels_masked = np.array([[0, 1, 0],
                              [0, 0, 1],
                              [-1, -1, -1],
                              [-1, -1, -1]])
    y_pred_masked = np.array([[0.05, 0.95, 0],
                              [0.1, 0.8, 0.1],
                              [0.1, 0.8, 0.1],
                              [0.05, 0.95, 0]], dtype=np.float32)

    f1_score_unmasked = tfa.metrics.F1Score(num_classes=3,
                                            average="macro",
                                            threshold=None)
    f1_score_unmasked.update_state(np.array(labels_unmasked),
                                   np.array(y_pred_unmasked))

    f1_score_masked = MaskedCategoricalF1Score(num_classes=3,
                                               metrics_precision=tf.float32,
                                               average="macro")
    f1_score_masked.update_state(np.array(labels_masked),
                                 np.array(y_pred_masked))

    expected_f1_score = 0.2222222
    np.testing.assert_almost_equal(f1_score_unmasked.result().numpy(),
                                   expected_f1_score)
    np.testing.assert_almost_equal(f1_score_masked.result().numpy(),
                                   expected_f1_score)
