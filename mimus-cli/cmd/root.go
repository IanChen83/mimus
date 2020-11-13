package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

// Execute executes the root command.
func Execute() {
	var rootCmd = &cobra.Command{
		Use:   "mimus",
		Short: "Short description",
		Long:  "Long description",

		// we handle error message by ourselves
		SilenceUsage:  true,
		SilenceErrors: true,
	}

	rootCmd.AddCommand(newInitCommand())

	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
