/*****************************************************************************
 * Copyright (c) 2014-2026 OpenRCT2 developers
 *
 * For a complete list of all authors, please refer to contributors.md
 * Interested in contributing? Visit https://github.com/OpenRCT2/OpenRCT2
 *
 * OpenRCT2 is licensed under the GNU General Public License version 3.
 *****************************************************************************/

#pragma once

#include <cassert>
#include <cstdint>
#include <span>

namespace OpenRCT2::Drawing
{
    enum class PaletteIndex : uint8_t;

    /**
     * Represents an 8-bit indexed map that maps from one palette index to another.
     */
    struct PaletteMap
    {
    private:
        std::span<PaletteIndex> _data{};
#ifdef _DEBUG
        // We only require those fields for the asserts in debug builds.
        size_t _numMaps{};
        size_t _mapLength{};
#endif

    public:
        static PaletteMap GetDefault();

        constexpr PaletteMap() = default;

        constexpr PaletteMap(PaletteIndex* data, size_t numMaps, size_t mapLength)
            : _data{ data, numMaps * mapLength }
#ifdef _DEBUG
            , _numMaps(numMaps)
            , _mapLength(mapLength)
#endif
        {
        }

        constexpr PaletteMap(std::span<PaletteIndex> map)
            : _data(map)
#ifdef _DEBUG
            , _numMaps(1)
            , _mapLength(map.size())
#endif
        {
        }

        // Called once per pixel by the remapping and blending blitters: keep these inline (the Amiga build has no
        // link-time optimisation, so an out-of-line definition costs a call per pixel).
        const PaletteIndex* data() const
        {
            return _data.data();
        }

        PaletteIndex& operator[](size_t index)
        {
            return _data[index];
        }
        PaletteIndex operator[](size_t index) const
        {
            return _data[index];
        }

        PaletteIndex Blend(PaletteIndex src, PaletteIndex dst) const
        {
            const auto srcValue = static_cast<size_t>(src);
            const auto dstValue = static_cast<size_t>(dst);
#ifdef _DEBUG
            assert(srcValue != 0);
            assert(srcValue - 1 < _numMaps);
            assert(dstValue < _mapLength);
#endif
            return _data[((srcValue - 1) * 256) + dstValue];
        }
        void Copy(PaletteIndex dstIndex, const PaletteMap& src, PaletteIndex srcIndex, size_t length);
    };
} // namespace OpenRCT2::Drawing
