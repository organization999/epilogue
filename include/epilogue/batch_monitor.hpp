#pragma once

#include <chrono>
#include <concepts>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace epilogue
{
  template <class Encoder, class Observation>
  concept ObservationEncoder =
    requires(const Observation& observation)
    {
      {
        Encoder::encode(observation)
      } -> std::convertible_to<std::string>;
    };

  /*
   * Batch-only observability ledger.
   *
   * Epilogue intentionally has no knowledge of the observed application's
   * types. Observation and Encoder are selected by the embedding project at
   * compile time. Encoder::encode() must return one valid JSON value.
   *
   * Records are retained in memory and written only when BatchSize is reached,
   * flush() is called, or the monitor is destroyed. There are no subscribers,
   * callbacks, background workers, or online analysis paths.
   */
  template <
    class Observation,
    class Encoder,
    std::size_t BatchSize = 256UL>
  requires ObservationEncoder<Encoder, Observation>
  class BatchMonitor final
  {
  private:
    struct Entry final
    {
      std::uint64_t sequence{0UL};
      std::int64_t timestamp_ns{0};
      std::string operation{};
      std::string observation{};
    };

  public:
    static_assert(
      0UL < BatchSize,
      "Epilogue BatchSize must be greater than zero");

    explicit BatchMonitor(
      std::filesystem::path path)
      : m_path(
          std::move(path))
    {}

    BatchMonitor(
      const BatchMonitor&) = delete;

    BatchMonitor(
      BatchMonitor&&) = delete;

    void operator=(
      const BatchMonitor&) = delete;

    void operator=(
      BatchMonitor&&) = delete;

    ~BatchMonitor() noexcept
    {
      try
      {
        flush();
      }
      catch (...)
      {
        /* Explicit flush() remains the reportable durability boundary. */
      }
    }

    void log(
      const std::string_view operation,
      const Observation& observation)
    {
      const std::string encoded =
        Encoder::encode(
          observation);

      const auto elapsed =
        std::chrono::system_clock::now()
          .time_since_epoch();

      const std::int64_t timestamp_ns =
        std::chrono::duration_cast<
          std::chrono::nanoseconds>(
            elapsed)
          .count();

      std::lock_guard<std::mutex>
        lock{
          m_mutex
        };

      m_entries.push_back(
        Entry{
          m_next_sequence++,
          timestamp_ns,
          std::string{
            operation
          },
          encoded
        });

      if (
        m_entries.size() >=
        BatchSize)
      {
        m_flush_unlocked();
      }
    }

    void flush(
      void)
    {
      std::lock_guard<std::mutex>
        lock{
          m_mutex
        };

      m_flush_unlocked();
    }

    [[nodiscard]] std::size_t pending(
      void) const
    {
      std::lock_guard<std::mutex>
        lock{
          m_mutex
        };

      return
        m_entries.size();
    }

    [[nodiscard]] const std::filesystem::path& path(
      void) const noexcept
    {
      return
        m_path;
    }

  private:
    static void m_write_json_string(
      std::ostream& stream,
      const std::string_view value)
    {
      stream.put('"');

      for (
        const unsigned char character :
        value)
      {
        switch (character)
        {
          case '"':
            stream << "\\\"";
            break;

          case '\\':
            stream << "\\\\";
            break;

          case '\b':
            stream << "\\b";
            break;

          case '\f':
            stream << "\\f";
            break;

          case '\n':
            stream << "\\n";
            break;

          case '\r':
            stream << "\\r";
            break;

          case '\t':
            stream << "\\t";
            break;

          default:
          {
            if (
              character <
              0x20U)
            {
              static constexpr char digits[]{
                "0123456789abcdef"
              };

              stream
                << "\\u00"
                << digits[(character >> 4U) & 0x0FU]
                << digits[character & 0x0FU];
            }
            else
            {
              stream.put(
                static_cast<char>(
                  character));
            }

            break;
          }
        }
      }

      stream.put('"');
    }

    void m_flush_unlocked(
      void)
    {
      if (
        true ==
        m_entries.empty())
      {
        return;
      }

      const std::filesystem::path parent =
        m_path.parent_path();

      if (
        false ==
        parent.empty())
      {
        std::filesystem::create_directories(
          parent);
      }

      std::ofstream stream{
        m_path,
        std::ios::binary |
        std::ios::app
      };

      if (
        false ==
        stream.good())
      {
        throw std::runtime_error(
          "unable to open Epilogue batch ledger");
      }

      for (
        const Entry& entry :
        m_entries)
      {
        stream
          << "{\"sequence\":"
          << entry.sequence
          << ",\"timestamp_ns\":"
          << entry.timestamp_ns
          << ",\"operation\":";

        m_write_json_string(
          stream,
          entry.operation);

        stream
          << ",\"observation\":"
          << entry.observation
          << "}\n";
      }

      stream.flush();

      if (
        false ==
        stream.good())
      {
        throw std::runtime_error(
          "failed to flush Epilogue batch ledger");
      }

      m_entries.clear();
    }

    std::filesystem::path
      m_path;

    std::vector<Entry>
      m_entries{};

    std::uint64_t
      m_next_sequence{0UL};

    mutable std::mutex
      m_mutex{};

  }; // class BatchMonitor final

} // namespace epilogue
