/*****************************************************************************
 * Copyright (c) 2014-2026 OpenRCT2 developers
 *
 * For a complete list of all authors, please refer to contributors.md
 * Interested in contributing? Visit https://github.com/OpenRCT2/OpenRCT2
 *
 * OpenRCT2 is licensed under the GNU General Public License version 3.
 *****************************************************************************/

#include "Drawing.Sprite.h"
#include "RenderTarget.h"

#include <cassert>
#include <cstring>

using namespace OpenRCT2::Drawing;

template<DrawBlendOp TBlendOp>
static void FASTCALL DrawRLESpriteMagnify(RenderTarget& rt, const DrawSpriteArgs& args)
{
    auto& paletteMap = args.PalMap;
    auto imgData = args.SourceImage.offset;
    auto* dst = reinterpret_cast<PaletteIndex*>(args.DestinationBits);
    auto srcX = args.SrcX;
    auto srcY = args.SrcY;
    auto width = args.Width;
    auto height = args.Height;
    auto zoom = rt.zoom_level;
    auto dstLineWidth = rt.LineStride();

    for (int32_t y = 0; y < height; y++)
    {
        PaletteIndex* nextDst = dst + dstLineWidth;
        const int32_t rowNum = zoom.ApplyTo(srcY + y);
        uint16_t lineOffset;
        std::memcpy(&lineOffset, &imgData[rowNum * sizeof(uint16_t)], sizeof(uint16_t));
        const uint8_t* data8 = imgData + lineOffset;

        bool lastDataForLine = false;
        int32_t numPixels = 0;
        uint8_t pixelRunStart = 0;
        for (int32_t x = 0; x < width; x++)
        {
            const int32_t colNum = zoom.ApplyTo(srcX + x);

            while (colNum >= pixelRunStart + numPixels && !lastDataForLine)
            {
                data8 += numPixels;
                numPixels = *data8++;
                pixelRunStart = *data8++;
                lastDataForLine = numPixels & 0x80;
                numPixels &= 0x7F;
            }
            if (pixelRunStart <= colNum && colNum < pixelRunStart + numPixels)
                BlitPixel<TBlendOp>(reinterpret_cast<const PaletteIndex*>(data8 + colNum - pixelRunStart), dst, paletteMap);
            dst++;
        }

        dst = nextDst;
    }
}

template<DrawBlendOp TBlendOp, size_t TZoom>
static void FASTCALL DrawRLESpriteMinify(RenderTarget& rt, const DrawSpriteArgs& args)
{
    auto src0 = args.SourceImage.offset;
    auto dst0 = args.DestinationBits;
    auto srcX = args.SrcX;
    auto srcY = args.SrcY;
    auto width = args.Width;
    auto height = args.Height;
    auto zoom = 1 << TZoom;
    auto dstLineWidth = static_cast<size_t>(rt.LineStride());

    // Move up to the first line of the image if source_y_start is negative. Why does this even occur?
    if (srcY < 0)
    {
        srcY += zoom;
        height -= zoom;
        dst0 += dstLineWidth;
    }

    // For every line in the image
    for (int32_t i = 0; i < height; i += zoom)
    {
        int32_t y = srcY + i;

        // The first part of the source pointer is a list of offsets to different lines
        // This will move the pointer to the correct source line.
        uint16_t lineOffset = src0[y * 2] | (src0[y * 2 + 1] << 8);
        auto nextRun = src0 + lineOffset;
        auto* dstLineStart = reinterpret_cast<PaletteIndex*>(dst0 + dstLineWidth * (i >> TZoom));

        // For every data chunk in the line
        auto isEndOfLine = false;
        while (!isEndOfLine)
        {
            // Read chunk metadata
            auto src = nextRun;
            auto dataSize = *src++;
            auto firstPixelX = *src++;
            isEndOfLine = (dataSize & 0x80) != 0;
            dataSize &= 0x7F;

            // Have our next source pointer point to the next data section
            nextRun = src + dataSize;

            int32_t x = firstPixelX - srcX;
            int32_t numPixels = dataSize;
            if (x > 0)
            {
                // If x is not a multiple of zoom, round it up to a multiple
                auto mod = x & (zoom - 1);
                if (mod != 0)
                {
                    auto offset = zoom - mod;
                    x += offset;
                    src += offset;
                    numPixels -= offset;
                }
            }
            else if (x < 0)
            {
                // Clamp x to zero if negative
                src += -x;
                numPixels += x;
                x = 0;
            }

            // If the end position is further out than the whole image
            // end position then we need to shorten the line again
            numPixels = std::min(numPixels, width - x);

            auto dst = dstLineStart + (x >> TZoom);
            if constexpr ((TBlendOp & kBlendSrc) == 0 && (TBlendOp & kBlendDst) == 0 && TZoom == 0)
            {
                // Since we're sampling each pixel at this zoom level, just do a straight std::memcpy
                if (numPixels > 0)
                {
                    std::memcpy(dst, src, numPixels);
                }
            }
#if defined(__amigaos__) || defined(OPENRCT2_RLE_FAST) // OPENRCT2_RLE_FAST: spike/rle/harness.cpp checks it natively
            else if constexpr (TBlendOp == (kBlendTransparent | kBlendSrc) && TZoom == 0)
            {
                // Remapped sprites (anything with a primary colour: guests, vehicles, most scenery) are half of all
                // sprites drawn. An RLE run holds no transparent source pixels (the plain path memcpys it), so only
                // the remapped value needs the transparency test; four pixels per iteration keeps the loop overhead
                // down on the 68k.
                const PaletteIndex* map = args.PalMap.data();
                for (; numPixels >= 4; numPixels -= 4, src += 4, dst += 4)
                {
                    const PaletteIndex p0 = map[src[0]];
                    const PaletteIndex p1 = map[src[1]];
                    const PaletteIndex p2 = map[src[2]];
                    const PaletteIndex p3 = map[src[3]];
                    if (p0 != PaletteIndex::transparent)
                        dst[0] = p0;
                    if (p1 != PaletteIndex::transparent)
                        dst[1] = p1;
                    if (p2 != PaletteIndex::transparent)
                        dst[2] = p2;
                    if (p3 != PaletteIndex::transparent)
                        dst[3] = p3;
                }
                for (; numPixels > 0; numPixels--, src++, dst++)
                {
                    const PaletteIndex p = map[src[0]];
                    if (p != PaletteIndex::transparent)
                        dst[0] = p;
                }
            }
#endif
            else
            {
                auto& paletteMap = args.PalMap;
                while (numPixels > 0)
                {
                    BlitPixel<TBlendOp>(reinterpret_cast<PaletteIndex*>(src), dst, paletteMap);
                    numPixels -= zoom;
                    src += zoom;
                    dst++;
                }
            }
        }
    }
}

template<DrawBlendOp TBlendOp>
static void FASTCALL DrawRLESprite(RenderTarget& rt, const DrawSpriteArgs& args)
{
    auto zoom_level = static_cast<int8_t>(rt.zoom_level);
    switch (zoom_level)
    {
        case -2:
        case -1:
            DrawRLESpriteMagnify<TBlendOp>(rt, args);
            break;
        case 0:
            DrawRLESpriteMinify<TBlendOp, 0>(rt, args);
            break;
        case 1:
            DrawRLESpriteMinify<TBlendOp, 1>(rt, args);
            break;
        case 2:
            DrawRLESpriteMinify<TBlendOp, 2>(rt, args);
            break;
        case 3:
            DrawRLESpriteMinify<TBlendOp, 3>(rt, args);
            break;
        default:
            assert(false);
            break;
    }
}

/**
 * Transfers readied images onto buffers
 * This function copies the sprite data onto the screen
 *  rct2: 0x0067AA18
 * @param imageId Only flags are used.
 */
void FASTCALL GfxRleSpriteToBuffer(RenderTarget& rt, const DrawSpriteArgs& args)
{
    if (args.Image.HasPrimary())
    {
        if (args.Image.IsBlended())
        {
            DrawRLESprite<kBlendTransparent | kBlendSrc | kBlendDst>(rt, args);
        }
        else
        {
            DrawRLESprite<kBlendTransparent | kBlendSrc>(rt, args);
        }
    }
    else if (args.Image.IsBlended())
    {
        DrawRLESprite<kBlendTransparent | kBlendDst>(rt, args);
    }
    else
    {
        DrawRLESprite<kBlendTransparent>(rt, args);
    }
}
