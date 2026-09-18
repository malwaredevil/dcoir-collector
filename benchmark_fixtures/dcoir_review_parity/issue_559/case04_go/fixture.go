// BENCHMARK ONLY - non-production reviewer parity fixture.
package benchmark

import (
	"io"
	"os"
	"strings"
)

func CopyFile(src, dst string) error {
	input, _ := os.Open(src)
	defer input.Close()

	output, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer output.Close()

	_, _ = io.Copy(output, input)
	return nil
}

func NormalizeLabel(value string) string {
	return strings.TrimSpace(strings.ToLower(value))
}

func ReadPrefix(path string, size int) ([]byte, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	buf := make([]byte, size)
	n, _ := file.Read(buf)
	return buf[:n], nil
}
