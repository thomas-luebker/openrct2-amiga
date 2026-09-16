/*****************************************************************************
 * Copyright (c) 2014-2026 OpenRCT2 developers
 *
 * For a complete list of all authors, please refer to contributors.md
 * Interested in contributing? Visit https://github.com/OpenRCT2/OpenRCT2
 *
 * OpenRCT2 is licensed under the GNU General Public License version 3.
 *****************************************************************************/

#pragma once

#include "../core/EnumUtils.hpp"
#include "../world/MapLimits.h"
#include "EntityBase.h"

#include <array>
#include <list>
#include <string>
#include <vector>

struct CoordsXY;

namespace OpenRCT2
{
    constexpr uint16_t kMaxEntities = 65535;
    constexpr uint16_t kMaxMiscEntities = 3200;

    constexpr const uint32_t kSpatialIndexSize = (kMaximumMapSizeTechnical * kMaximumMapSizeTechnical) + 1;
    constexpr uint32_t kSpatialIndexNullBucket = kSpatialIndexSize - 1;

    constexpr uint32_t kInvalidSpatialIndex = 0xFFFFFFFFu;
    constexpr uint32_t kSpatialIndexDirtyMask = 1u << 31;

    // Every entity lives in a slot of this size, whatever type it is, and the store is
    // kMaxEntities of them whether the park holds four guests or four thousand. Upstream's 512 bytes
    // leaves 180 unused per slot on a 32-bit build, where the largest type, a guest, is 332 -- which
    // is 11 MB of a 68k's memory spent on padding. EntityRegistry.cpp asserts at compile time that
    // every entity type still fits, so this cannot silently become too small.
#ifdef __amigaos__
    constexpr size_t kEntitySlotSize = 352;
#else
    constexpr size_t kEntitySlotSize = 0x200;
#endif

    union Entity_t
    {
        uint8_t pad00[kEntitySlotSize];
        EntityBase base;
        Entity_t()
            : pad00()
        {
        }
    };

#pragma pack(push, 1)
    struct EntitiesChecksum
    {
        std::array<std::byte, 20> raw;

        std::string toString() const;
    };
#pragma pack(pop)

    template<typename T>
    class EntityList;

    class EntityRegistry
    {
    private:
        Entity_t entities[kMaxEntities]{};
        std::array<std::list<EntityId>, EnumValue(EntityType::count)> gEntityLists;
        std::vector<EntityId> _freeIdList;

        bool _entityFlashingList[kMaxEntities];

        // Sized for the map that is loaded rather than for the largest the engine can hold. Upstream's
        // fixed 1001x1001 costs 1,002,002 empty vectors -- 11.5 MB on a 32-bit target -- whether the park
        // is 256 tiles across or 1000. resetEntitySpatialIndices() sets the stride and the size together,
        // and it is the only place either changes; every lookup goes through computeSpatialIndex().
        // Starts at the size of a standard RCT2 map so every lookup is in range before the first park is
        // loaded; resetEntitySpatialIndices() then sizes it to whatever map actually arrives.
        static constexpr uint32_t kDefaultSpatialStride = 256;
        std::vector<std::vector<EntityId>> gEntitySpatialIndex
            = std::vector<std::vector<EntityId>>(kDefaultSpatialStride * kDefaultSpatialStride + 1);
        uint32_t _spatialStride = kDefaultSpatialStride;

    public:
        uint16_t getEntityListCount(EntityType type);
        uint16_t getNumFreeEntities();

        EntityBase* getEntity(EntityId entityId);

        template<typename T>
        T* getEntity(EntityId entityId)
        {
            auto* ent = getEntity(entityId);
            if (ent == nullptr)
            {
                return nullptr;
            }
            if constexpr (std::is_same_v<T, EntityBase>)
            {
                return ent;
            }
            else
            {
                return ent->as<T>();
            }
        }

        EntityBase* tryGetEntity(EntityId spriteIndex);

        template<typename T>
        T* tryGetEntity(EntityId entityId)
        {
            auto* ent = tryGetEntity(entityId);
            if (ent == nullptr)
            {
                return nullptr;
            }
            if constexpr (std::is_same_v<T, EntityBase>)
            {
                return ent;
            }
            else
            {
                return ent->as<T>();
            }
        }

        const std::vector<EntityId>& getEntityTileList(const CoordsXY& spritePos);

        EntityBase* createEntity(EntityType type);

        template<typename T>
        T* createEntity()
        {
            return static_cast<T*>(createEntity(T::kEntityType));
        }

        // Use only with imports that must happen at a specified index
        EntityBase* createEntityAt(EntityId index, EntityType type);
        // Use only with imports that must happen at a specified index
        template<typename T>
        T* createEntityAt(EntityId index)
        {
            return static_cast<T*>(createEntityAt(index, T::kEntityType));
        }

        const std::list<EntityId>& getEntityList(EntityType id);
        uint16_t getMiscEntityCount();

        void resetAllEntities();
        void resetEntitySpatialIndices();
        uint32_t computeSpatialIndex(const CoordsXY& loc) const;
        uint32_t spatialNullBucket() const
        {
            return _spatialStride * _spatialStride;
        }

#if !defined(DISABLE_NETWORK) || defined(__amigaos__) || defined(OPENRCT2_KEEP_CHECKSUM)

        template<typename T>
        void networkSerialseEntityType(DataSerialiser& ds)
        {
            for (auto* ent : EntityList<T>())
            {
                ent->serialise(ds);
            }
        }

        template<typename... T>
        void networkSerialiseEntityTypes(DataSerialiser& ds)
        {
            (networkSerialseEntityType<T>(ds), ...);
        }

#endif // DISABLE_NETWORK

        EntitiesChecksum getAllEntitiesChecksum();

        template<typename T>
        void miscUpdateAllType()
        {
            for (auto misc : EntityList<T>())
            {
                misc->update();
            }
        }

        template<typename... T>
        void miscUpdateAllTypes()
        {
            (miscUpdateAllType<T>(), ...);
        }

        void updateAllMiscEntities();
        void updateMoneyEffect();
        void entityRemove(EntityBase* entity);
        uint16_t removeFloatingEntities();
        void updateEntitiesSpatialIndex();
        void updateEntitySpatialIndex(EntityBase& entity);

        void entitySetFlashing(EntityBase* entity, bool flashing);
        bool entityGetFlashing(EntityBase* entity);

    private:
        void resetEntityLists();
        void resetFreeIds();
        void entityReset(EntityBase& entity);
        void addToEntityList(EntityBase& entity);
        void addToFreeList(EntityId index);
        void removeFromEntityList(EntityBase& entity);
        void prepareNewEntity(EntityBase& base, EntityType type);
        void entitySpatialInsert(EntityBase& entity, const CoordsXY& newLoc);
        void entitySpatialRemove(EntityBase& entity);
        void freeEntity(EntityBase& entity);
    };

} // namespace OpenRCT2
