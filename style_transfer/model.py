# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license.

# Original source: https://github.com/pytorch/examples/blob/master/fast_neural_style/neural_style/neural_style.py
import os
import re
import sys

import fire
import torch
from torchvision import transforms

from style_transfer import load_image, save_image


class TransformerNet(torch.nn.Module):
    def __init__(self):
        super(TransformerNet, self).__init__()
        # Initial convolution layers
        self.conv1 = ConvLayer(3, 32, kernel_size=9, stride=1)
        self.in1 = torch.nn.InstanceNorm2d(32, affine=True)
        self.conv2 = ConvLayer(32, 64, kernel_size=3, stride=2)
        self.in2 = torch.nn.InstanceNorm2d(64, affine=True)
        self.conv3 = ConvLayer(64, 128, kernel_size=3, stride=2)
        self.in3 = torch.nn.InstanceNorm2d(128, affine=True)
        # Residual layers
        self.res1 = ResidualBlock(128)
        self.res2 = ResidualBlock(128)
        self.res3 = ResidualBlock(128)
        self.res4 = ResidualBlock(128)
        self.res5 = ResidualBlock(128)
        # Upsampling Layers
        self.deconv1 = UpsampleConvLayer(128, 64, kernel_size=3, stride=1, upsample=2)
        self.in4 = torch.nn.InstanceNorm2d(64, affine=True)
        self.deconv2 = UpsampleConvLayer(64, 32, kernel_size=3, stride=1, upsample=2)
        self.in5 = torch.nn.InstanceNorm2d(32, affine=True)
        self.deconv3 = ConvLayer(32, 3, kernel_size=9, stride=1)
        # Non-linearities
        self.relu = torch.nn.ReLU()

    def forward(self, X):
        y = self.relu(self.in1(self.conv1(X)))
        y = self.relu(self.in2(self.conv2(y)))
        y = self.relu(self.in3(self.conv3(y)))
        y = self.res1(y)
        y = self.res2(y)
        y = self.res3(y)
        y = self.res4(y)
        y = self.res5(y)
        y = self.relu(self.in4(self.deconv1(y)))
        y = self.relu(self.in5(self.deconv2(y)))
        y = self.deconv3(y)
        return y


class ConvLayer(torch.nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, stride):
        super(ConvLayer, self).__init__()
        reflection_padding = kernel_size // 2
        self.reflection_pad = torch.nn.ReflectionPad2d(reflection_padding)
        self.conv2d = torch.nn.Conv2d(in_channels, out_channels, kernel_size, stride)

    def forward(self, x):
        out = self.reflection_pad(x)
        out = self.conv2d(out)
        return out


class ResidualBlock(torch.nn.Module):
    """ResidualBlock
    introduced in: https://arxiv.org/abs/1512.03385
    recommended architecture: http://torch.ch/blog/2016/02/04/resnets.html
    """

    def __init__(self, channels):
        super(ResidualBlock, self).__init__()
        self.conv1 = ConvLayer(channels, channels, kernel_size=3, stride=1)
        self.in1 = torch.nn.InstanceNorm2d(channels, affine=True)
        self.conv2 = ConvLayer(channels, channels, kernel_size=3, stride=1)
        self.in2 = torch.nn.InstanceNorm2d(channels, affine=True)
        self.relu = torch.nn.ReLU()

    def forward(self, x):
        residual = x
        out = self.relu(self.in1(self.conv1(x)))
        out = self.in2(self.conv2(out))
        out = out + residual
        return out


class UpsampleConvLayer(torch.nn.Module):
    """UpsampleConvLayer
    Upsamples the input and then does a convolution. This method gives better results
    compared to ConvTranspose2d.
    ref: http://distill.pub/2016/deconv-checkerboard/
    """

    def __init__(self, in_channels, out_channels, kernel_size, stride, upsample=None):
        super(UpsampleConvLayer, self).__init__()
        self.upsample = upsample
        if upsample:
            self.upsample_layer = torch.nn.Upsample(
                mode="nearest", scale_factor=upsample
            )
        reflection_padding = kernel_size // 2
        self.reflection_pad = torch.nn.ReflectionPad2d(reflection_padding)
        self.conv2d = torch.nn.Conv2d(in_channels, out_channels, kernel_size, stride)

    def forward(self, x):
        x_in = x
        if self.upsample:
            x_in = self.upsample_layer(x_in)
        out = self.reflection_pad(x_in)
        out = self.conv2d(out)
        return out


def load_model(model_dir, style, cuda=True):
    device = torch.device("cuda" if cuda else "cpu")
    with torch.no_grad():
        style_model = TransformerNet()
        state_dict = torch.load(os.path.join(model_dir, style + ".pth"))
        # remove saved deprecated running_* keys in InstanceNorm from the checkpoint
        for k in list(state_dict.keys()):
            if re.search(r"in\d+\.running_(mean|var)$", k):
                del state_dict[k]
        style_model.load_state_dict(state_dict)
        style_model.to(device)
        return style_model


def stylize_batch(style_model, img_batch, cuda=True):
    device = torch.device("cuda" if cuda else "cpu")
    with torch.no_grad():
        content_batch = torch.FloatTensor(img_batch).mul(1 / 255)
        content_image = content_batch.to(device)
        output = style_model(content_image).cpu()
        return output


def stylize(style_model, img, cuda=True):
    device = torch.device("cuda" if cuda else "cpu")
    with torch.no_grad():
        content_transform = transforms.Compose(
            [transforms.ToTensor(), transforms.Lambda(lambda x: x.mul(255))]
        )
        content_image = content_transform(img)
        content_image = content_image.unsqueeze(0).to(device)

        output = style_model(content_image).cpu()
        return output


def clean_gpu_mem():
    torch.cuda.empty_cache()


def main(
    content_dir=os.getenv("CONTENT_PATH", "content"),
    model_dir=os.getenv("MODEL_PATH", "model"),
    style="mosaic",
    output_dir=os.getenv("OUTPUT_PATH", "output"),
    cuda=True,
):
    """

    :param content_dir:
    :param model_dir:
    :param style: one of candy, mosaic, rain_princess, udnie
    :param output_dir:
    :return:
    """

    filenames = os.listdir(content_dir)
    style_model = load_model(model_dir, style, cuda=cuda)
    for filename in filenames:
        print("Processing {}".format(filename))
        full_path = os.path.join(content_dir, filename)
        content_image = load_image(full_path)
        styled_image = stylize(style_model, content_image)
        output_path = os.path.join(output_dir, filename)
        save_image(output_path, styled_image[0])

    if cuda and not torch.cuda.is_available():
        print("ERROR: cuda is not available, try running on CPU")
        sys.exit(1)


if __name__ == "__main__":
    fire.Fire(main)
