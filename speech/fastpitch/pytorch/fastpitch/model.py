# Copyright (c) 2021 Graphcore Ltd. All rights reserved.
# This file has been modified by Graphcore Ltd.
# *****************************************************************************
#  Copyright (c) 2020, NVIDIA CORPORATION.  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#      * Redistributions of source code must retain the above copyright
#        notice, this list of conditions and the following disclaimer.
#      * Redistributions in binary form must reproduce the above copyright
#        notice, this list of conditions and the following disclaimer in the
#        documentation and/or other materials provided with the distribution.
#      * Neither the name of the NVIDIA CORPORATION nor the
#        names of its contributors may be used to endorse or promote products
#        derived from this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#  ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#  WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL NVIDIA CORPORATION BE LIABLE FOR ANY
#  DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#  ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# *****************************************************************************


import torch
from torch import nn as nn
import torch.nn.functional as F

from common.layers import ConvReLUNorm
from fastpitch.transformer import FFTransformer


def regulate_len(durations, enc_out, pace=1.0, mel_max_len=None):
    """If target=None, then predicted durations are applied"""
    dtype = enc_out.dtype
    reps = durations.float() / pace
    reps = (reps + 0.5).long()
    dec_lens = reps.sum(dim=1)
    max_len = 870
    reps_cumsum = torch.cumsum(F.pad(reps, (1, 0, 0, 0), value=0.0), dim=1)[:, None, :]
    reps_cumsum = reps_cumsum.to(dtype)
    range_ = torch.arange(max_len)[None, :, None]  # TODO check process
    mult = ((reps_cumsum[:, :, :-1] <= range_) &
            (reps_cumsum[:, :, 1:] > range_))
    mult = mult.to(dtype)
    enc_rep = torch.matmul(mult, enc_out)

    if mel_max_len:
        enc_rep = enc_rep[:, :mel_max_len]
        dec_lens = torch.clamp_max(dec_lens, mel_max_len)
    return enc_rep, dec_lens


class TemporalPredictor(nn.Module):
    """Predicts a single float per each temporal location"""

    def __init__(self, input_size, filter_size, kernel_size, dropout,
                 n_layers=2):
        super(TemporalPredictor, self).__init__()

        self.layers = nn.Sequential(*[
            ConvReLUNorm(input_size if i == 0 else filter_size, filter_size,
                         kernel_size=kernel_size, dropout=dropout)
            for i in range(n_layers)]
        )
        self.fc = nn.Linear(filter_size, 1, bias=True)

    def forward(self, enc_out, enc_out_mask):
        out = enc_out * enc_out_mask
        out = self.layers(out.transpose(1, 2)).transpose(1, 2)
        out = self.fc(out) * enc_out_mask
        return out.squeeze(-1)


class FastPitch(nn.Module):
    def __init__(self, n_mel_channels, max_seq_len, n_symbols, padding_idx,
                 symbols_embedding_dim, in_fft_n_layers, in_fft_n_heads,
                 in_fft_d_head,
                 in_fft_conv1d_kernel_size, in_fft_conv1d_filter_size,
                 in_fft_output_size,
                 p_in_fft_dropout, p_in_fft_dropatt, p_in_fft_dropemb,
                 out_fft_n_layers, out_fft_n_heads, out_fft_d_head,
                 out_fft_conv1d_kernel_size, out_fft_conv1d_filter_size,
                 out_fft_output_size,
                 p_out_fft_dropout, p_out_fft_dropatt, p_out_fft_dropemb,
                 dur_predictor_kernel_size, dur_predictor_filter_size,
                 p_dur_predictor_dropout, dur_predictor_n_layers,
                 pitch_predictor_kernel_size, pitch_predictor_filter_size,
                 p_pitch_predictor_dropout, pitch_predictor_n_layers,
                 pitch_embedding_kernel_size, n_speakers, speaker_emb_weight):
        super(FastPitch, self).__init__()
        del max_seq_len  # unused

        self.encoder = FFTransformer(
            n_layer=in_fft_n_layers, n_head=in_fft_n_heads,
            d_model=symbols_embedding_dim,
            d_head=in_fft_d_head,
            d_inner=in_fft_conv1d_filter_size,
            kernel_size=in_fft_conv1d_kernel_size,
            dropout=p_in_fft_dropout,
            dropatt=p_in_fft_dropatt,
            dropemb=p_in_fft_dropemb,
            embed_input=True,
            d_embed=symbols_embedding_dim,
            n_embed=n_symbols,
            padding_idx=padding_idx)

        if n_speakers > 1:
            self.speaker_emb = nn.Embedding(n_speakers, symbols_embedding_dim)
        else:
            self.speaker_emb = None
        self.speaker_emb_weight = speaker_emb_weight

        self.duration_predictor = TemporalPredictor(
            in_fft_output_size,
            filter_size=dur_predictor_filter_size,
            kernel_size=dur_predictor_kernel_size,
            dropout=p_dur_predictor_dropout, n_layers=dur_predictor_n_layers
        )

        self.decoder = FFTransformer(
            n_layer=out_fft_n_layers, n_head=out_fft_n_heads,
            d_model=symbols_embedding_dim,
            d_head=out_fft_d_head,
            d_inner=out_fft_conv1d_filter_size,
            kernel_size=out_fft_conv1d_kernel_size,
            dropout=p_out_fft_dropout,
            dropatt=p_out_fft_dropatt,
            dropemb=p_out_fft_dropemb,
            embed_input=False,
            d_embed=symbols_embedding_dim
        )

        self.pitch_predictor = TemporalPredictor(
            in_fft_output_size,
            filter_size=pitch_predictor_filter_size,
            kernel_size=pitch_predictor_kernel_size,
            dropout=p_pitch_predictor_dropout, n_layers=pitch_predictor_n_layers
        )

        self.pitch_emb = nn.Conv1d(
            1, symbols_embedding_dim,
            kernel_size=pitch_embedding_kernel_size,
            padding=int((pitch_embedding_kernel_size - 1) / 2))

        # Store values precomputed for training data within the model
        self.register_buffer('pitch_mean', torch.zeros(1))
        self.register_buffer('pitch_std', torch.zeros(1))

        self.proj = nn.Linear(out_fft_output_size, n_mel_channels, bias=True)

    def forward(self, inputs, use_gt_durations=True, use_gt_pitch=True,
                pace=1.0, max_duration=75):
        inputs, mel_tgt, dur_tgt, pitch_tgt = inputs
        mel_max_len = mel_tgt.size(2)

        # Calculate speaker embedding
        spk_emb = 0
        # Input FFT
        enc_out, enc_mask = self.encoder(inputs, conditioning=spk_emb)

        # Embedded for predictors
        pred_enc_out, pred_enc_mask = enc_out, enc_mask

        # Predict durations
        log_dur_pred = self.duration_predictor(pred_enc_out, pred_enc_mask)
        dur_pred = torch.clamp(torch.exp(log_dur_pred) - 1, 0, max_duration)

        # Predict pitch
        pitch_pred = self.pitch_predictor(enc_out, enc_mask)

        if use_gt_pitch and pitch_tgt is not None:
            pitch_emb = self.pitch_emb(pitch_tgt.unsqueeze(1))
        else:
            pitch_emb = self.pitch_emb(pitch_pred.unsqueeze(1))
        enc_out = enc_out + pitch_emb.transpose(1, 2)

        len_regulated, dec_lens = regulate_len(
            dur_tgt if use_gt_durations else dur_pred,
            enc_out, pace, mel_max_len)

        # Output FFT
        dec_out, dec_mask = self.decoder(len_regulated, dec_lens)
        mel_out = self.proj(dec_out)
        return mel_out, log_dur_pred, pitch_pred
