#include <epilogue/batch_monitor.hpp>

#include <cassert>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace
{
  struct Observation final
  {
    int value{0};
  };

  struct Encoder final
  {
    [[nodiscard]] static std::string encode(
      const Observation& observation)
    {
      return
        "{\"value\":" +
        std::to_string(
          observation.value) +
        "}";
    }
  };

  [[nodiscard]] std::vector<std::string> read_lines(
    const std::filesystem::path& path)
  {
    std::ifstream stream{
      path,
      std::ios::binary
    };

    assert(
      true ==
      stream.good());

    std::vector<std::string> lines{};
    std::string line{};

    while (
      std::getline(
        stream,
        line))
    {
      lines.push_back(
        line);
    }

    return
      lines;
  }
}

int main()
{
  const auto suffix =
    std::chrono::steady_clock::now()
      .time_since_epoch()
      .count();

  const std::filesystem::path path =
    std::filesystem::temp_directory_path() /
    (
      "epilogue-batch-monitor-" +
      std::to_string(
        suffix) +
      ".ndjson"
    );

  using Monitor =
    epilogue::BatchMonitor<
      Observation,
      Encoder,
      2UL>;

  {
    Monitor monitor{
      path
    };

    monitor.log(
      "execute",
      Observation{
        1
      });

    assert(
      1UL ==
      monitor.pending());

    monitor.log(
      "execute",
      Observation{
        2
      });

    assert(
      0UL ==
      monitor.pending());

    const auto first_batch =
      read_lines(
        path);

    assert(
      2UL ==
      first_batch.size());

    assert(
      std::string::npos !=
      first_batch[0].find(
        "\"operation\":\"execute\""));

    assert(
      std::string::npos !=
      first_batch[0].find(
        "\"observation\":{\"value\":1}"));

    monitor.log(
      "execute",
      Observation{
        3
      });

    assert(
      1UL ==
      monitor.pending());

    monitor.flush();

    assert(
      0UL ==
      monitor.pending());
  }

  const auto complete_ledger =
    read_lines(
      path);

  assert(
    3UL ==
    complete_ledger.size());

  std::filesystem::remove(
    path);

  return 0;
}
